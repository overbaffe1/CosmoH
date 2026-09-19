# GitVerse — чистая передача Космоконтура

**Команда #🦥🛰ЛЕНИВЫЕ В ОРБИТЕ**

Репозиторий: <https://gitverse.ru/hackrus.experts/kosmo-piter_lenivye_v_orbite_197>

Логин владельца: `DPAKYJIA`.

## 0. Сначала безопасность

Если токен был отправлен в чат, **отзовите его в GitVerse**. Создайте новый с минимальными
правами на запись в нужный репозиторий. Не вставляйте токен в URL, команды, `.env`, README
или сообщения. Пароль/токен вводится только в интерактивный запрос Git на вашем компьютере.
Альтернатива — SSH: добавьте свой публичный ключ в GitVerse, возьмите SSH Clone URL из
интерфейса репозитория. Приватный ключ никому не передавайте.

Здесь нет сохранённых ключей или токенов. В Arena публикация подготовлена, но **в GitVerse
не выполнена**. Авторизация GitHub не является авторизацией GitVerse.

## 1. Какой комплект загружать

Используйте `fuel-contour-submission.zip` — автономный архив **только Космоконтура**,
без `.git`, виртуального окружения и истории других проектов. В корне архива сразу лежат
`README.md`, `GITVERSE.md`, `fuel/`, `web/`, `configs/`, `tests/`, `tools/`, `docs/`,
`vendor/`, `references/` и контрольные результаты. Не загружайте старую историю CosmoH.

При необходимости собрать архив самостоятельно, из каталога решения в исходном клоне:

```bash
# Из корня CosmoH сначала: cd solutions/fuel-contour
bash tools/setup.sh
.venv/bin/python -m fuel.cli suite --output results
.venv/bin/python tools/package.py
```

Архив: `results/fuel-contour-submission.zip`. Результаты сборки не загружаются автоматически.
Готовые PDF/PPTX включены. Для их обновления — отдельные команды в RUNBOOK.md.

## 2. Распаковать в НОВЫЙ каталог и проверить

Команды для Bash / Git Bash / WSL на **вашем компьютере**, не внутри старого CosmoH.
Понадобятся Git, Python 3.11+ и unzip. Сохраните скачанный архив в текущий каталог.

```bash
mkdir kosmokontur-gitverse
unzip fuel-contour-submission.zip -d kosmokontur-gitverse
cd kosmokontur-gitverse
python3 tools/verify_submission.py
bash tools/setup.sh
.venv/bin/python tools/verify_vendor.py
.venv/bin/python -m pytest -q
```

Проверка manifest должна пройти ДО изменения файлов. Она проверяет SHA256 всех файлов архива,
включая документы и исходники. Новый компьютер может требовать `python` вместо `python3`.
На Windows предпочтительнее WSL: команды установки используют `.venv/bin/python`.

## 3. Создать чистую историю и отправить

Эти команды публикуют **только отдельную ветку `arena/01a0b7c5-cosmoh`**, не изменяют main,
не переписывают историю и не применяют force. Начните в только что распакованной папке:

```bash
git init -b arena/01a0b7c5-cosmoh

# Если Git попросит авторство, укажите своё настоящее имя и email локально:
# git config user.name "Ваше имя"
# git config user.email "Ваш email"

git add .
# Только эти контрольные результаты входят в сдаваемый ZIP;
# остальные временные результаты остаются под .gitignore.
git add -f results/summary.json results/comparison.csv results/decision_brief.json \
  results/earth results/lunar results/recourse

git diff --cached --stat
git commit -m "Космоконтур 2035 — ЛЕНИВЫЕ В ОРБИТЕ"
git remote add gitverse https://gitverse.ru/hackrus.experts/kosmo-piter_lenivye_v_orbite_197.git

# Git интерактивно попросит новый токен как пароль; его ввод не отображается.
# Пустой helper запрещает сохранять его через credential helper для этой команды.
git -c credential.helper= -c credential.username=DPAKYJIA \
  push -u gitverse arena/01a0b7c5-cosmoh
```

Если эта ветка уже существует с другими коммитами, Git отклонит push. **Не добавляйте `--force`**:
сначала сохраните локальную работу и разберите различия с владельцем репозитория.
Если появляется 401/403 — проверьте отзыв старого токена, права нового и членство в проекте;
не присылайте секреты в чат. Имя автора коммита не даёт права доступа к репозиторию.

Для SSH вместо HTTPS используйте SSH URL из кнопки Clone в GitVerse:
`git remote set-url gitverse <SSH-URL-ИЗ-GITVERSE>`, затем обычный
`git push -u gitverse arena/01a0b7c5-cosmoh`.

## 4. Обязательно после push

1. Откройте GitVerse и выберите опубликованную ветку `arena/01a0b7c5-cosmoh`.
2. Если главная страница показывает прежний README, назначьте опубликованную ветку
   веткой по умолчанию через настройки репозитория либо согласуйте с владельцем
   платформенный запрос на слияние. Не считайте push в отдельную ветку автоматической сдачей.
3. Проверьте README, `docs/PRESENTATION.pdf` (10 слайдов), PPTX, `docs/TALK_4_MIN.txt`,
   `docs/REPORT.pdf` (10 страниц), `docs/COMPARISON.pdf` (1 страница), код и конфигурации.
4. Проверьте доступ жюри к репозиторию и правильность ссылки в форме сдачи.
5. Клонируйте выбранную ветку заново и повторите установку/pytest. Сохраните хеш коммита.

`.github/workflows/` описывает проверку для GitHub Actions. Работа этого workflow в GitVerse
не проверена и не обещана; используйте явные команды RUNBOOK, не выдавайте наличие YAML за CI.

## 5. Запуск сайта из чистого комплекта

```bash
.venv/bin/python -m uvicorn fuel.api:app --host 0.0.0.0 --port 8000
```

Открыть на том же компьютере <http://localhost:8000>. Для Arena — Live Preview порта 8000.
Это локальный прототип, не постоянный публичный хостинг и не многопользовательский сервис.
GitVerse хранит исходники, но сам push не запускает FastAPI в Интернете.

## 6. Честный статус проверки

Собственные тесты и неизменность 37 + 3 файлов проверяются отдельно от внешнего validator:

```bash
bash tools/check.sh
```

Общий код **1** ожидается на отсутствующей ссылке
`vendor/test_oil/data/README.md → ../docs/ERRATA_AND_PROVENANCE.md`.
Перед ней семь проверок организатора проходят; свои тесты должны пройти отдельно.
Не добавляйте фиктивный документ и не скрывайте этот сбой. Все ограничения — в RUNBOOK
и `docs/VERIFICATION.md`.
