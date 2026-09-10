# Arquitetura

## Decisões

O Django renderiza HTML no servidor. Cada página compartilha o documento e o shell; páginas de planejamento estendem uma composição comum. A navegação funciona com links normais e os filtros usam query strings compartilháveis. JavaScript acrescenta interações locais, modais, gráficos e gravação assíncrona; não há bundler obrigatório no runtime.

O CSS parte de tokens semânticos em `variables.css`. Componentes são separados por responsabilidade e reunidos em `app.css`. Regras de responsividade ficam em `responsive.css`; a landing tem seu próprio arquivo para não carregar estilos de marketing no aplicativo.

## Responsabilidades

| Camada         | Responsabilidade                                              |
| -------------- | ------------------------------------------------------------- |
| Modelos        | Estrutura persistente, propriedade dos registros e restrições |
| Formulários    | Validação de entrada compartilhada pelos endpoints            |
| Serviços       | Períodos, totais, patrimônio, agrupamentos e score            |
| Views          | Autenticação, composição de contexto e adaptação HTTP         |
| Templates      | Semântica, hierarquia e apresentação                          |
| Componentes JS | HTTP, feedback, modais, busca e preferências locais           |
| Charts         | Adaptação dos dados calculados para Chart.js                  |

`Transaction` representa movimentações. `PortfolioItem` representa registros simples de planejamento com campos explícitos, discriminados por tipo. Antes de adicionar regras específicas como parcelas, manutenção de veículos ou itinerários, introduza entidades de domínio específicas com migrações; não acumule regras não relacionadas no registro genérico.

## Persistência e isolamento

Toda leitura ou mutação financeira é filtrada pelo usuário autenticado. A identidade nunca é aceita pelo formulário. A demonstração usa um usuário diferente por sessão e senha inutilizável. Os endpoints de escrita exigem POST e CSRF. Valores monetários usam `Decimal` e `DecimalField`; a conversão para float ocorre somente na camada de gráfico.

Preferências de widgets pertencem à conta. A opção de ocultar valores pertence ao navegador e usa localStorage. Dados financeiros persistem no banco, não no navegador. Ocultar valores é um recurso visual; não substitui controle de acesso.

Os dados de gráfico são serializados por `json_script`. Conteúdo do usuário é escapado pelo Django; o JavaScript usa `textContent` e criação de elementos. Exportações CSV neutralizam prefixos de fórmulas em campos textuais.

## Extensão

Para adicionar uma página, determine primeiro se ela pode reutilizar `base.html` ou `portfolio_base.html`. Para uma nova interação, prefira os helpers existentes em `utils.js` e os controladores de `components.js`/`records.js`. Para uma nova regra financeira, acrescente-a aos serviços e escreva um teste que demonstre o resultado esperado.

Recorrências, faturas e reservas desta versão são registros manuais. Um futuro ledger com transferências, contas e reconciliação exigirá uma modelagem própria para manter consistência contábil e evitar dupla contagem. Essas funcionalidades não devem ser simuladas no frontend.

## Evolução para operação comercial

Antes de um lançamento público: validar layouts em navegadores/dispositivos reais, adicionar testes de interação, revisar acessibilidade, implementar recuperação de conta e controles contra abuso, automatizar backups e migrações, observar erros/latência e definir retenção de dados. A infraestrutura de produção é separada da aplicação local entregue.
