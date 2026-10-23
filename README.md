# MangaDex-dl GTK

Interface GTK 4 em Python para MangaDex e Comick, com leitor interno, gerenciamento de MDLists e download via `mangadex-downloader`.

## Dependências

- Python 3.10+
- PyGObject + GTK 4 (`sudo apt install python3-gi gir1.2-gtk-4.0`)
- [mangadex-downloader](https://github.com/mansuf/mangadex-downloader) (`pipx install mangadex-downloader`)

## Instalação

```bash
pip install -e .
# ou com deps de dev
pip install -e ".[dev]"
```

## Rodar

```bash
# via entrypoint
mangadex-dl-gtk
# ou direto
python3 app.py
```

## Configuração

- Config em `XDG_CONFIG_HOME/mangadex_dl/config.json` (default `~/.config/mangadex_dl/config.json`)
- Variável `MANGADEX_DL_CONFIG` sobrepõe o path
- Legacy `config.json` na raiz é migrado automaticamente
- Exemplo em `config.json.example`

```json
{
  "default_download_folder": "/home/user/Downloads/manga",
  "ui_language": "pt-BR",
  "source": "mangadex"
}
```

## Atalhos Leitor

- Clique esquerda/direita na página para voltar/avançar
- `Esc` volta da conta/lista

## Desenvolvimento

```bash
ruff check .
mypy .
pytest
```

Estrutura: `app.py` + `services/` (API), `core/` (config/cache/download), `ui/` (home/result/reader/account), `assets/`, `style.css`.
