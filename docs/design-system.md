# Design System GenFin

## Direção

Superfícies escuras, bordas discretas, azul como ação principal e tipografia Inter. O foco é a leitura dos números e o acesso rápido às tarefas. Cor comunica estado sem substituir rótulos e ícones.

## Fundação

| Token      | Valor     | Uso                       |
| ---------- | --------- | ------------------------- |
| Background | `#05070D` | Plano de fundo            |
| Surface    | `#0B1224` | Cards, painéis e modais   |
| Primary    | `#4F7CFF` | Ação principal e foco     |
| Success    | `#22C55E` | Entradas e conclusão      |
| Danger     | `#EF4444` | Erros e ações destrutivas |
| Warning    | `#F59E0B` | Pendências                |
| Text       | `#FFFFFF` | Hierarquia principal      |
| Muted      | `#94A3B8` | Conteúdo secundário       |

Espaçamento em escala de 4px, com intervalos de 8, 12, 16, 20, 24, 32, 40 e 48px. Cantos de 6px para detalhes, 8px para controles, 12px para cards e 16px para modais. Valores monetários usam números tabulares e formatação brasileira.

## Biblioteca

| Componente                        | Implementação                                     |
| --------------------------------- | ------------------------------------------------- |
| Metric Card                       | `components/metric.html`, `cards.css`             |
| Glass Card                        | `.glass-card`                                     |
| Button / Badge                    | `buttons.css`                                     |
| Input / Select / Checkbox / Radio | `forms.css`                                       |
| Table                             | `components/transaction_table.html`, `tables.css` |
| Modal / Drawer                    | Elemento `dialog`, `modal.css`                    |
| Toast                             | `utils.js`, região live                           |
| Notification                      | `notifications.js`, painel na navbar              |
| Timeline / Progress               | `cards.css`                                       |
| Search                            | `components/search.html`, `components.js`         |
| Tabs                              | `buttons.css`, `charts.js`, navegação por setas   |
| Dropdown                          | `details`/`summary` com fechamento externo        |
| Avatar                            | Iniciais determinísticas e cores da marca         |
| Sidebar / Navbar                  | Includes compartilhados                           |
| Chart / Heatmap                   | `charts.css`, `charts.js` e dados do servidor     |

## Estados

Botões têm hover, pressionado, foco, desabilitado e submissão. Formulários preservam os dados em caso de erro, mostram uma mensagem e direcionam o foco ao campo inválido. Exclusões usam confirmação com o nome do registro. Telas sem dados orientam o primeiro cadastro. Falhas de carregamento do Chart.js mantêm os totais legíveis.

Modais nativos contêm o foco e fecham por Escape. A navegação móvel usa overlay, controle de foco e Escape. O atalho de busca é `Ctrl/Cmd+K`. Transições usam 180ms; a preferência `prefers-reduced-motion` reduz animações.

## Responsividade

- Acima de 1600px: superfície de trabalho limitada, com mais respiro.
- Até 1250px: navegação mais compacta e gráficos ajustados.
- Até 1050px: Dashboard em uma coluna com widgets auxiliares reorganizados.
- Até 800px: sidebar em drawer e cabeçalho móvel.
- Até 540px: formulários e cards em coluna; métricas em duas colunas; tabelas com rolagem local.

A página `/design-system/` permite explorar os componentes e seus estados. O tema escuro é a experiência validada por código nesta entrega; tokens de tema claro são uma base de extensão, sem alternância oferecida no produto.
