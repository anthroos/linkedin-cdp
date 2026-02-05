# LinkedIn CDP Automation

Автоматизація LinkedIn повідомлень через Chrome DevTools Protocol (CDP).

## Як це працює

```
┌─────────────────┐     WebSocket      ┌─────────────────┐
│  Python Script  │ ◄────────────────► │  Google Chrome  │
│  (linkedin_cdp) │     CDP Protocol   │  (debugging on) │
└─────────────────┘                    └────────┬────────┘
                                                │
                                                ▼
                                       ┌─────────────────┐
                                       │    LinkedIn     │
                                       │   (logged in)   │
                                       └─────────────────┘
```

1. **Chrome** запускається з флагом `--remote-debugging-port=9222`
2. **Python скрипт** підключається до Chrome через WebSocket
3. Скрипт надсилає **CDP команди** (клік, друк, навігація)
4. Chrome виконує команди на сторінці LinkedIn
5. Всі дії виглядають як **людські** (затримки, повільний друк)

## Структура файлів

```
~/tools/
├── README.md              # Ця документація
├── chrome_debug.sh        # Скрипт запуску Chrome з debugging
├── linkedin_cdp.py        # Основний CDP модуль
└── linkedin_send.py       # Приклад скрипта для розсилки
```

## Встановлення

### 1. Залежності

```bash
pip3 install websocket-client requests
```

### 2. Запуск Chrome з debugging

**Перший раз** (створює новий профіль):
```bash
chmod +x ~/tools/chrome_debug.sh
~/tools/chrome_debug.sh
```

Або вручну:
```bash
open -a 'Google Chrome' --args \
    --remote-debugging-port=9222 \
    --remote-allow-origins=\* \
    --user-data-dir="$HOME/chrome-debug-profile"
```

**ВАЖЛИВО:** 
- Це створює **окремий профіль** Chrome
- Потрібно **один раз залогінитись** в LinkedIn в цьому профілі
- Логін зберігається в `~/chrome-debug-profile/`

### 3. Перевірка що Chrome готовий

```bash
curl -s http://localhost:9222/json/version | python3 -c "import sys,json; print(json.load(sys.stdin).get('Browser'))"
```

Має вивести: `Chrome/xxx.x.xxxx.xxx`

## Використання

### Через Python

```python
import sys
sys.path.insert(0, '/Users/YOUR_USERNAME/tools')
from linkedin_cdp import LinkedInBot

bot = LinkedInBot()
bot.connect()

# Відправити повідомлення в поточну розмову
bot.send_message("Hello!")

# Клікнути на розмову по індексу (1 = перша)
bot.click_conversation(2)

# Знайти елемент по CSS селектору
bot.click_element('button.msg-form__send-button')

bot.close()
```

### Через Claude Code (Cursor/Clawdbot)

```
Запусти Python скрипт:
cd ~/tools && python3 -c "
import sys
sys.path.insert(0, '.')
from linkedin_cdp import LinkedInBot
bot = LinkedInBot()
bot.connect()
bot.send_message('Your message here')
bot.close()
"
```

## API Reference

### LinkedInBot

| Метод | Опис |
|-------|------|
| `connect()` | Підключитись до Chrome |
| `send_message(text)` | Надрукувати і відправити повідомлення |
| `click_conversation(index)` | Клікнути на розмову (1-based) |
| `click_element(selector)` | Клікнути елемент по CSS селектору |
| `type_text(text)` | Надрукувати текст (human-like) |
| `focus_message_input()` | Фокус на поле вводу |
| `find_element(selector)` | Знайти елемент |
| `close()` | Закрити з'єднання |

### Human-like поведінка

Вбудовані затримки:
- Між символами: 80-200ms
- Після пробілів: 150-350ms
- Після пунктуації: 200-450ms
- Періодичні "думаючі" паузи: 300-600ms
- Перед кліком Send: 600-1200ms

## Troubleshooting

### "Connection failed"
- Перевір що Chrome запущений з `--remote-debugging-port=9222`
- Перевір `curl http://localhost:9222/json`

### "WebSocket 403 Forbidden"
- Додай флаг `--remote-allow-origins=*` при запуску Chrome

### Кліки не працюють
- LinkedIn динамічно змінює DOM
- Спробуй інші CSS селектори
- Використай `bot._evaluate('javascript code')` для JS

### Новий профіль Chrome
- Треба залогінитись в LinkedIn один раз
- Логін зберігається в `~/chrome-debug-profile/`

## Безпека

⚠️ **Важливо:**
- Не комітьте `chrome-debug-profile/` (там ваші cookies!)
- Додайте в `.gitignore`: `chrome-debug-profile/`
- Не використовуйте для спаму
- LinkedIn може заблокувати акаунт при підозрілій активності

## Ліміти LinkedIn

Рекомендації щоб уникнути блокування:
- Не більше 50-100 повідомлень на день
- Затримки між повідомленнями: 3-10 секунд
- Не надсилайте однаковий текст всім
- Персоналізуйте повідомлення
