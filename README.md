# GenFin

Aplicação financeira criada do zero com **Django, PostgreSQL, HTML5, CSS puro e JavaScript ES6**. Interface em português, tema escuro, Inter, Font Awesome e Chart.js hospedados no próprio projeto. Sem Bootstrap, Tailwind, jQuery ou framework de frontend.

## Executar no Windows

Para hospedar, siga o [guia de deploy no Easypanel](docs/easypanel.md). O repositório inclui Dockerfile, Gunicorn e configuração de HTTPS por proxy.

A integração [Open Finance com Pluggy](docs/open-finance.md) está disponível, com sandbox como padrão. Configure as credenciais no servidor e execute o importador para conectar instituições de teste.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d
.\scripts\start.ps1
```

Acesse **http://127.0.0.1:8000/**. Use **Explorar demonstração** para uma conta temporária com dados fictícios, ou crie uma conta vazia. A demonstração cria dados separados para cada sessão; nenhuma senha pública é usada.

Se o PostgreSQL já estiver configurado em `.env`, basta executar `scripts/start.ps1`. O script aplica as migrações antes de iniciar o servidor de desenvolvimento.

### PostgreSQL sem Docker

Em Windows sem Docker funcional, `python scripts/setup_postgres.py` instala os binários oficiais da EDB em `%LOCALAPPDATA%\GenFin\postgres17`, cria um banco isolado em `127.0.0.1:5433` e gera `.env` com credenciais aleatórias. Execute **antes de criar `.env`**. O script preserva configurações e clusters existentes. Não instala serviço de sistema e mantém os dados fora do OneDrive.

Depois de reiniciar o computador, inicie esse banco com:

```powershell
& "$env:LOCALAPPDATA\GenFin\postgres17\pgsql\bin\pg_ctl.exe" -D "$env:LOCALAPPDATA\GenFin\postgres17\data" -l "$env:LOCALAPPDATA\GenFin\postgres17\postgres.log" start
.\scripts\start.ps1
```

Para parar o banco, substitua `start` por `stop -m fast`. Para parar o Django, use `Ctrl+C` no terminal.

### Preview sem banco PostgreSQL

```powershell
.\scripts\start.ps1 -Preview
```

Esse modo explícito usa SQLite em `preview.sqlite3`, somente para desenvolvimento. A execução normal usa PostgreSQL. Os dois bancos não compartilham dados.

## O que está implementado

- Design System navegável em `/design-system/`, biblioteca própria de componentes, sidebar e navbar compartilhadas.
- Dashboard com receitas, despesas, saldo, patrimônio, fluxo acumulado/diário, score interno, categorias, rankings, heatmap, timeline, metas, alertas, últimas movimentações e seleção persistente de widgets.
- Login, cadastro, logout via POST, perfil editável e landing page.
- Em Meu Perfil, **Resetar conta** exige a senha atual, desconecta as instituições da Pluggy e apaga transações, importações, cartões, veículos, viagens, receitas/despesas fixas, reservas, metas e preferências do dashboard. O perfil e o acesso são preservados. A exclusão é permanente; se a desconexão remota falhar, os dados locais são preservados para uma nova tentativa.
- Criação, edição, exclusão, busca, filtros, paginação e exportação CSV de transações.
- Cadastro, edição e exclusão de cartões, veículos, viagens, despesas fixas, receitas fixas e reservas.
- Feedback de sucesso/erro, validação no navegador e servidor, estados vazios, modais nativos, drawer, busca rápida `Ctrl/Cmd+K` e opção local de ocultar valores.
- Layouts CSS para desktop, notebook, tablet e celular; navegação móvel com controle de foco; respeito a movimento reduzido.
- Modelos com valores decimais, índices, restrições de banco, migrações e consultas vinculadas ao usuário autenticado.

## Estrutura

```text
genfin/                  Configuração Django, URLs e WSGI
finance/                 Modelos, formulários, serviços, views e testes
  migrations/            Evolução do esquema
  templatetags/          Formatação de moeda e helpers de apresentação
assets/
  css/                   Tokens e estilos separados por responsabilidade
  js/                    ES modules e controladores dos componentes
  vendor/                Inter, Font Awesome, Chart.js e licenças
templates/
  components/            Fragmentos compartilhados
  document.html          Documento HTML e assets
  base.html              Shell autenticado
  portfolio_base.html    Composição comum às telas de planejamento
  *.html                 Todas as páginas solicitadas
scripts/                 Inicialização, assets e verificação
docs/                    Arquitetura e Design System
```

## Regras financeiras

- **Saldo do mês:** receitas concluídas menos despesas concluídas no período selecionado.
- **Patrimônio líquido:** saldo acumulado até o final do período + reservas externas + valores estimados dos veículos − faturas cadastradas. Bens, reservas e faturas usam seus valores atuais; não há snapshots históricos desses registros.
- **Reservas:** saldos mantidos fora da conta de movimentações. Não cadastre o mesmo dinheiro como receita e como reserva externa para evitar dupla contagem.
- **Viagens:** orçamento de planejamento; não entra novamente no patrimônio.
- **Despesas e receitas fixas:** previsões mensais. Não geram transações automaticamente. O pagamento/recebimento deve ser registrado em Transações.
- **Cartões:** faturas e limites manuais. A integração Pluggy exibe contas/cartões em Open Finance e importa movimentações de contas bancárias em reais; compras de cartão e parcelas não são importadas.
- **Custo mensal do veículo:** soma de transações concluídas nas categorias IPVA, Seguro veicular e Combustível, vinculadas ao veículo e datadas no mês escolhido. IPVA e seguro entram pelo pagamento (ou parcela), sem rateio anual. Use os atalhos na aba Veículos ou selecione o veículo ao lançar a despesa em Transações. Edição, exclusão e mudança de status atualizam o mesmo registro, sem duplicação. Despesas antigas precisam ter a categoria e o veículo definidos manualmente; não há associação por nome. Excluir o veículo preserva as transações financeiras e remove seu vínculo.
- **Score:** indicador interno explicável (capacidade de poupança até 60 pontos e proporção de registros concluídos até 40). Não é score de crédito nem recomendação financeira.
- **Heatmap:** 91 dias de despesas concluídas até o final do mês escolhido; intensidade baseada no valor diário.

## Verificação

```powershell
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py test finance
.\.venv\Scripts\python manage.py collectstatic --noinput
npm install
npm run check:js
npm run format:check
```

Os testes cobrem cálculos decimais, pendências, isolamento entre contas, CRUD, validação, CSRF, filtros, CSV, preferências, demonstração, cadastro, autenticação e renderização de todas as rotas.

Para testar sem PostgreSQL, defina `$env:USE_SQLITE='True'` na sessão de teste. Para testes PostgreSQL, o usuário de teste precisa de permissão `CREATEDB`.

## Manutenção

`requirements.txt` define faixas compatíveis; `requirements.lock.txt` registra as versões Python verificadas nesta entrega. `package-lock.json` fixa a ferramenta de formatação. Dependências visuais já estão incluídas e podem ser reproduzidas com `python scripts/vendor_assets.py`.

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m ruff format genfin finance scripts
.\.venv\Scripts\python -m djlint templates --reformat
npm run format
```

## Limites de operação

Esta entrega é uma aplicação local funcional. Publicação, domínio, e-mail transacional, recuperação de senha, MFA, verificação de e-mail, limitação de tentativas de login e cobrança de assinatura não estão configurados. A integração bancária com Pluggy exige credenciais próprias e um processo de importação ativo; consulte o [guia Open Finance](docs/open-finance.md).

Para produção, use servidor WSGI, PostgreSQL gerenciado ou operado com backups, HTTPS, `GENFIN_DEBUG=False`, uma `SECRET_KEY` privada e `ALLOWED_HOSTS` explícitos. Defina uma política de retenção para contas de demonstração; o comando `purge_demo_accounts` remove demonstrações inativas há mais de sete dias. O servidor `runserver` é apenas para desenvolvimento.

Referências técnicas: [Django](https://docs.djangoproject.com/en/5.2/), [Chart.js](https://www.chartjs.org/docs/latest/), [PostgreSQL para Windows](https://www.postgresql.org/download/windows/).
