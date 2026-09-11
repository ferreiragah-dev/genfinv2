# Open Finance com Pluggy

O GenFin usa o Pluggy Connect para autorização e a API REST no Django para importar dados. As credenciais da aplicação ficam somente no servidor; o navegador recebe um Connect Token temporário. A implementação segue o [fluxo oficial do widget](https://docs.pluggy.ai/docs/setup-pluggyconnect-widget-on-your-app) e o [exemplo HTML da Pluggy](https://github.com/pluggyai/quickstart/blob/master/frontend/html/index.html).

## Ativar o sandbox

1. Crie uma aplicação de testes no [dashboard da Pluggy](https://dashboard.pluggy.ai/) e obtenha o Client ID e Client Secret.
2. Preencha no `.env` local, ou nas variáveis de ambiente do servidor:

```dotenv
PLUGGY_CLIENT_ID=seu_client_id
PLUGGY_CLIENT_SECRET=seu_client_secret
PLUGGY_SANDBOX=True
```

3. Aplique as migrações e inicie o site normalmente:

```powershell
.\scripts\start.ps1
```

4. Em outro terminal, na pasta do projeto, mantenha o importador em execução:

```powershell
.\.venv\Scripts\python manage.py sync_pluggy --watch
```

Se estiver usando `start.ps1 -Preview`, defina `$env:USE_SQLITE='True'` também no terminal do importador. Os dois processos precisam usar o mesmo banco e as mesmas variáveis.

5. Entre com uma conta pessoal, abra **Open Finance** e clique em **Conectar instituição**. Contas temporárias de demonstração não podem criar conexões, nem no sandbox.
6. Selecione **Pluggy Bank**. Use `user-ok`, senha `password-ok` e, quando solicitado, código `123456`, conforme o [guia de sandbox](https://docs.pluggy.ai/docs/sandbox).
7. Após concluir, aguarde a importação. Confira as contas nesta tela e os lançamentos em **Transações** e no dashboard. Repita **Importar dados** para verificar que os mesmos IDs não geram novos lançamentos.

O modo sandbox filtra os conectores do widget e recusa instituições reais no servidor. Use também uma aplicação sandbox da própria Pluggy: os filtros do widget não substituem as permissões do provedor. Os dados fictícios importados entram nos cálculos da conta pessoal usada para testar.

## Sincronização

As conexões ficam em uma fila persistente no banco. O comando `sync_pluggy --watch` consulta essa fila a cada cinco segundos. Também é possível agendar `python manage.py sync_pluggy` a cada minuto; ele processa somente conexões com importação pendente/vencida. Execuções concorrentes usam uma reserva por conexão, com expiração para recuperação após interrupções.

Após uma importação bem-sucedida, o GenFin consulta novamente os dados disponíveis na Pluggy em seis horas. **Importar dados** antecipa essa leitura; **Renovar conexão** abre o widget para atualizar a coleta na instituição ou resolver consentimento/MFA. A coleta automática da instituição pela Pluggy depende da aplicação e do plano contratado; consulte [atualização de Items](https://docs.pluggy.ai/docs/item). Não há webhook nesta versão: o importador consulta os dados periodicamente.

Movimentações usam [`GET /v2/transactions`](https://docs.pluggy.ai/reference/transactions-list-by-cursor), com paginação por cursor, preservando o filtro de conta e de datas. O endpoint antigo paginado não é utilizado. São importados os últimos 90 dias, com valores decimais e datas convertidas para `America/Sao_Paulo`. O histórico mais antigo já importado é preservado.

O commit acontece somente depois de obter todas as páginas e verificar que o Item continua atualizado. IDs existentes são atualizados; registros removidos pela Pluggy desaparecem do GenFin somente dentro da janela completamente consultada. Falhas preservam o snapshot anterior e deixam uma mensagem na tela. Lançamentos importados são protegidos contra edição/exclusão manual para manter a próxima sincronização consistente.

## Escopo financeiro

- Contas `BANK` em `BRL`: importação de receitas/despesas, concluídas ou pendentes, categorizadas inicialmente como **Outros**.
- Contas e cartões: nome, tipo, moeda e saldo disponível na Pluggy são exibidos em Open Finance. CPF, credenciais bancárias e payloads completos não são armazenados pelo GenFin.
- Compras de cartão e investimentos não entram no dashboard nesta versão. Isso evita lançar compras de cartão novamente junto com a saída bancária do pagamento da fatura.
- Saldos da instituição não são somados ao patrimônio calculado a partir dos lançamentos. O saldo do dashboard representa o fluxo registrado, não o saldo bancário disponível.
- Não há conversão cambial, categorização automática, conciliação com lançamentos manuais, nem identificação de transferências entre contas próprias. Essas transferências aparecem como entrada/saída e podem aumentar os totais de receitas e despesas.
- A deduplicação usa o ID da movimentação da Pluggy dentro da mesma conexão. Não conecte a mesma conta por instituições/Items diferentes: essa situação e lançamentos manuais equivalentes exigem conciliação adicional.

**Desconectar** remove o Item na Pluggy, interrompe novas importações e preserva o histórico local. Uma falha remota mantém a conexão ativa para permitir nova tentativa. Para mudar de sandbox para dados reais, use uma conta GenFin separada para não misturar os históricos.

Para começar novamente na mesma conta, vá a **Meu Perfil → Resetar conta**, leia a confirmação e digite sua senha do GenFin. Esse reset desconecta todas as instituições e apaga permanentemente todos os dados financeiros, incluindo o histórico importado e as preferências do dashboard. Nome, e-mail, login e senha são preservados. Importações em andamento e retornos antigos do widget não podem restaurar os dados. Se alguma desconexão na Pluggy falhar, os dados locais são preservados; algumas instituições podem já ter sido desconectadas, e o reset pode ser tentado novamente. Contas temporárias de demonstração não podem usar o reset.

## Easypanel

Configure as três variáveis Pluggy no serviço web. Crie um serviço App adicional, `pluggy-worker`, com a mesma origem/imagem e as mesmas variáveis de banco, Django e Pluggy. Use o comando de inicialização:

```sh
python manage.py sync_pluggy --watch
```

Não configure domínio ou porta pública para o worker. Faça primeiro o deploy do web, que aplica as migrações, depois inicie o worker. Como alternativa, agende o comando sem `--watch`. Sem worker/agendador, a autorização funciona, mas as importações ficam aguardando.

## Contas reais

Depois de validar o sandbox, configure as credenciais da aplicação de produção da Pluggy e `PLUGGY_SANDBOX=False` no web e no worker, reinicie ambos e conecte uma instituição em uma conta GenFin limpa. O modo real lista somente conectores com `isOpenFinance=True` e `isSandbox=False`. Configure na Pluggy as permissões/domínios exigidos pela aplicação, usando o endereço HTTPS do site. A ativação real e um teste ponta a ponta dependem dessas credenciais e da autorização do titular.

## Verificação

```powershell
$env:USE_SQLITE='True'
.\.venv\Scripts\python manage.py test finance
npm run check:js
npm run test:open-finance
```

Os testes usam respostas simuladas da API para verificar autenticação, CSRF, vínculo entre usuário e Item, sandbox, paginação, isolamento, valores decimais, reconciliação, rollback e desconexão. Eles não substituem a validação pelo widget com uma aplicação Pluggy configurada.
