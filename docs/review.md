# Revisar movimentações

Abra **Revisar movimentações** no menu ou pelo botão em **Transações**. A página `/review/` funciona com formulários HTML, sem dependência de JavaScript para enviar as decisões.

## Categorias

A aba **Categorias** mostra movimentações ainda não revisadas. Use os filtros de descrição, mês e **Todas as categorias** para encontrar e corrigir uma movimentação já classificada.

Selecione uma categoria e clique em **Salvar e marcar como revisada**. IPVA, seguro veicular e combustível exigem uma despesa vinculada a um veículo da mesma conta. Essas despesas passam a compor os custos do veículo.

A escolha fica marcada como personalizada e tem prioridade sobre regras e sincronizações. Valor, data, descrição e status de registros bancários continuam sob controle da instituição. Categorizar não altera esses dados nem envia alterações à Pluggy.

## Regras automáticas

Crie uma regra ao revisar uma movimentação ou na aba **Regras automáticas**. Informe o texto que a descrição deve conter, o tipo (receita/despesa), a categoria e, quando necessário, o veículo.

Exemplo: descrição contém `netflix`, tipo **Despesa**, categoria **Lazer**. A comparação ignora maiúsculas e acentos. Quando mais de uma regra combina, a criada mais recentemente tem prioridade; editar uma regra mantém sua posição nessa ordem.

Salvar uma regra aplica a classificação aos registros existentes que combinam e não têm categoria personalizada. A regra também vale para as próximas importações. As categorias manuais existentes são preservadas pela migração; novos lançamentos manuais usam a categoria escolhida no formulário. Remover uma regra preserva as classificações já atribuídas e interrompe sua aplicação futura. Excluir um veículo também remove as regras vinculadas a ele.

## Duplicatas e transferências

As sugestões comparam valores iguais e datas com até três dias de diferença. Isso é apenas uma aproximação e sempre exige confirmação do usuário. Os filtros de mês e descrição selecionam os lançamentos de origem; a busca por correspondências também considera datas próximas fora do mês selecionado.

- **Duplicata:** um lançamento manual e um importado do mesmo tipo. Ao confirmar, o manual fica fora dos totais e o importado serve como referência. Se o manual tem categoria personalizada e o importado ainda não, essa categoria e o veículo são copiados para o importado.
- **Transferência interna:** saída e entrada concluídas, de mesmo valor, em duas contas bancárias importadas diferentes do mesmo usuário. Confirme somente se os registros representam o mesmo dinheiro movimentado entre suas próprias contas. Ambas as pontas ficam fora dos totais de receitas e despesas.
- **Não estão relacionados:** descarta apenas essa sugestão, sem alterar dados ou totais. O botão de reexibir sugestões permite reconsiderar as decisões descartadas.

Cada página analisa até 15 lançamentos de origem e mostra até cinco correspondências por lançamento. Avance pelas páginas para analisar os demais registros. A revisão não conecta automaticamente as contas nem identifica a titularidade real com base em CPF.

## Histórico e reversão

Os registros permanecem em Transações e no CSV. A coluna **Conciliação** informa se o registro entra nos totais, é uma duplicata conciliada ou uma transferência interna. Dashboard, gráficos, categorias, notificações e custos de veículos respeitam essas decisões.

Em **Decisões**, use **Desfazer conciliação**. Uma transferência pode coexistir com duplicatas manuais apontando para o mesmo registro bancário: desfazer uma decisão preserva as demais. Categorias copiadas durante a conciliação são mantidas ao desfazer.

Se uma movimentação muda de valor, data, tipo, status, descrição ou conta, as conciliações e sugestões descartadas relacionadas a ela são invalidadas. Se uma movimentação é removida, as conciliações relacionadas são removidas e os registros restantes voltam a ser contabilizados conforme suas outras decisões. Um formulário aberto antes de uma alteração precisa ser atualizado antes da confirmação.

Sincronizações idênticas preservam as decisões. Categorias personalizadas acompanham o ID da transação; se a instituição substituir o ID, o novo registro é tratado como uma nova movimentação e passa pelas regras/revisão novamente.

O **Resetar conta** também apaga regras, conciliações e sugestões descartadas, somente para o usuário que confirmou a senha.

## Atualização no Easypanel

Atualize o site e o `pluggy-worker` para a mesma versão. Para esta mudança de esquema, pare o worker antigo, faça o deploy do site (que aplica as migrações `0005` e `0006`) e então atualize e inicie o worker. A migração preserva as categorias manuais já existentes. Nenhuma nova credencial ou serviço é necessário.

## Verificação

```powershell
.\.venv\Scripts\python manage.py test finance
npm run check:js
npm run test:open-finance
```

Os testes cobrem isolamento, CSRF, formulários desatualizados, regras, prioridades, categorias e veículos, duplicatas, transferências, descarte, reversão, alterações e remoções bancárias, sincronizações repetidas e reset. As chamadas à Pluggy são simuladas.
