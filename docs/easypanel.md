# Deploy do GenFin no Easypanel

Use um projeto com dois serviços: um App Django e um Postgres. O Dockerfile usa Gunicorn, coleta os assets com WhiteNoise e aplica as migrações ao iniciar. A imagem não inclui o `.env` nem o banco da máquina de desenvolvimento.

Para ativar o Open Finance, configure também as credenciais Pluggy e um worker conforme o [guia da integração](open-finance.md#easypanel).

## 1. Banco

Crie o projeto `genfin` e um serviço Postgres chamado `db`, com a imagem `postgres:17-alpine`. Aguarde o banco iniciar. Em Credentials, copie o host interno, nome do banco, usuário e senha. Mantenha a conexão pela rede interna do projeto.

## 2. Aplicativo

Crie um serviço App chamado `web`. Configure a origem GitHub:

| Campo              | Valor                      |
| ------------------ | -------------------------- |
| Repositório        | `ferreiragah-dev/genfinv2` |
| Branch             | `main`                     |
| Build Path         | `/`                        |
| Builder            | Dockerfile                 |
| Arquivo Dockerfile | `Dockerfile`               |

Para repositórios privados, conecte o GitHub conforme indicado pelo Easypanel. Deixe o comando de inicialização sem override: o Dockerfile já define o comando. Comece com uma réplica; para múltiplas réplicas, mova as migrações para uma etapa única de release antes de escalar.

## 3. Variáveis

Em Environment do serviço `web`, preencha os valores reais:

```dotenv
GENFIN_DEBUG=False
USE_SQLITE=False
SECRET_KEY=SUBSTITUA_POR_UMA_CHAVE_ALEATORIA
ALLOWED_HOSTS=genfin.seudominio.com
CSRF_TRUSTED_ORIGINS=https://genfin.seudominio.com
TRUST_PROXY=True
POSTGRES_HOST=HOST_INTERNO_COPIADO_DO_BANCO
POSTGRES_PORT=5432
POSTGRES_DB=NOME_COPIADO_DO_BANCO
POSTGRES_USER=USUARIO_COPIADO_DO_BANCO
POSTGRES_PASSWORD=SENHA_COPIADA_DO_BANCO
PORT=8000
WEB_CONCURRENCY=2
```

Gere uma chave única no seu terminal e copie apenas para Environment:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Não envie as credenciais para o GitHub. A aplicação usa as variáveis `POSTGRES_*`; configurar somente `DATABASE_URL` não basta. O host do banco deve ser o host interno informado pelo painel, não `localhost` nem `127.0.0.1`.

`TRUST_PROXY=True` permite ao Django reconhecer o HTTPS terminado pelo proxy. Use somente com o proxy do Easypanel controlando os cabeçalhos e sem exposição pública direta da porta do aplicativo.

## 4. Domínio

Em Domains, configure o domínio público, HTTPS, caminho `/`, protocolo interno HTTP e porta de destino `8000`. Para domínio próprio, aponte o registro DNS ao servidor. Também é possível usar o domínio automático do Easypanel, substituindo o host nos dois campos de domínio das variáveis.

`ALLOWED_HOSTS` recebe hosts sem protocolo; `CSRF_TRUSTED_ORIGINS` recebe origens completas com `https://`. Para vários domínios, separe os valores por vírgulas. Não publique a porta 8000 em Advanced/Ports; o acesso ocorre pelo proxy em Domains.

## 5. Deploy e verificação

Com o banco ativo, salve as configurações e clique em Deploy no aplicativo. Confira o build e os logs de execução. O início deve mostrar migrações, coleta de estáticos e Gunicorn ouvindo em `0.0.0.0:8000`.

Abra o domínio, crie uma conta e teste um lançamento. O banco começa vazio: os registros do PostgreSQL local não são enviados pelo GitHub.

Para criar um administrador, abra Shell no serviço App e execute:

```sh
python manage.py createsuperuser
```

Depois, acesse `/admin/`. Configure backups do serviço Postgres antes de usar dados reais. A demonstração cria contas temporárias; o comando `python manage.py purge_demo_accounts` pode ser agendado para limpeza de contas inativas.

## Diagnóstico

| Sintoma                    | Verificação                                                          |
| -------------------------- | -------------------------------------------------------------------- |
| 502                        | Gunicorn iniciado, domínio apontando para HTTP/8000, banco acessível |
| 400 / DisallowedHost       | Host público presente em `ALLOWED_HOSTS`                             |
| Loop de redirecionamento   | `TRUST_PROXY=True` e cabeçalho HTTPS correto no proxy                |
| 403 ao enviar formulário   | Origem HTTPS correta em `CSRF_TRUSTED_ORIGINS`                       |
| Falha ao conectar no banco | Host interno e credenciais do serviço Postgres                       |
| CSS/ícones ausentes        | Etapa `collectstatic` concluída nos logs                             |

Referências: [App no Easypanel](https://easypanel.io/docs/services/app), [Postgres no Easypanel](https://easypanel.io/docs/services/postgres), [proxy HTTPS no Django](https://docs.djangoproject.com/en/5.2/ref/settings/#secure-proxy-ssl-header).
