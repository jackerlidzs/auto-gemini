# BitBrowser Automation Tool

![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.12-blue.svg)

This is a Python/PyQt6-based automation management tool for BitBrowser, supporting batch window creation, automatic proxy assignment, automated SheerID verification link extraction, and account eligibility checking.

Tutorial Documentation: https://docs.qq.com/doc/DSEVnZHprV0xMR05j?no_promotion=1&is_blank_or_template=blank

---

## 📢 Advertisement

🏆 **Recommended: BitBrowser** - Fingerprint browser designed for cross-border e-commerce & social media marketing
👉 **[Register Here](https://www.bitbrowser.cn/?code=vl9b7j)**

💳 **Virtual Card Recommendation - HolyCard** - Supports Gemini subscription, GPT Team, 0$ Plus, as low as 2R per card
👉 **[Apply Now](https://www.holy-card.com/)**

*(Register through this link for official support and discounts)*

---

## ✨ Features

* **Batch Window Creation**:
  * **Template Clone**: Clone windows by entering a template window ID.
  * **Default Template**: Built-in universal template for quick one-click creation.
* **Smart Naming**:
  * **Custom Prefix**: Enter window name prefix (e.g., "StoreA") to auto-generate "StoreA_1", "StoreA_2".
  * **Auto Numbering**: Uses template name or "Default Template" with sequential numbers if no prefix specified.
* **Automated Configuration**: Automatically reads `accounts.txt` and `proxies.txt` for batch account and proxy binding.
* **2FA Code Management**: Automatically extracts keys from browser remarks or config, batch generates and saves 2FA codes.
* **SheerID Link Extraction**:
  * Fully automated: Open browser -> Google login -> Navigate to activity page -> Extract verification link.
  * **Precise Status Detection**: Automatically distinguishes 5 account statuses:
    1. 🔗 **Eligible Pending Verification**: SheerID verification link obtained.
    2. ✅ **Verified Unbound**: Eligible and verified (shows "Get student offer").
    3. 💳 **Subscribed (Card Bound)**: Already subscribed/card bound.
    4. ❌ **Ineligible**: Detected "This offer is not available".
    5. ⏳ **Timeout/Error**: Detection timeout (10s) or other extraction errors.
  * **Multi-language Support**: Built-in multi-language keyword library with auto-translation fallback, supports global language interface detection.
* **🎯 Auto Card Binding** (NEW!):
  * **Smart iframe Detection**: Automatically handles Google Payments' complex nested iframe structure.
  * **One-Click Binding**: Automatically fills card number, expiry date, CVV and submits.
  * **Subscription Activation**: Automatically clicks subscribe button to complete the flow.
  * **Error Handling**: Supports various page structures, adapts to different account states.
* **📊 Web Admin Interface** (NEW!):
  * **Database Management**: SQLite database as single source of truth, auto-syncs with text files.
  * **Real-time Viewing**: Visit `http://localhost:8080` to view all account statuses.
  * **Filter & Search**: Support filtering by status, keyword search.
  * **Batch Export**: One-click export of qualifying account data.
  * **Click to Copy**: All fields support one-click copy for efficiency.
  * **Auto Start**: Web service starts automatically in background with GUI.
* **Batch Operations**: Support batch open, close, delete windows.

## 🛠️ Installation & Usage

### Method 1: Direct Run (Recommended)

No Python environment needed, just download and run the `.exe` file from Releases.

1. Download `BitBrowserAutoManager.exe`.
2. Prepare config files in the same directory (see below).
3. Double-click to run.

### Method 2: Run from Source

1. Clone repository:
   ```bash
   git clone https://github.com/yourusername/bitbrowser-auto-manager.git
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run:
   ```bash
   python create_window_gui.py
   ```

## ⚙️ Configuration

Create the following files in the program directory:

### 1. `accounts.txt` (Account Information)

**📌 Separator Configuration**

Configure separator on the **first line** (uncomment one):

```text
# Separator configuration (uncomment one)
separator="----"
# separator="---"
# separator="|"
# separator=","
```

**📋 Account Format**

Format (fixed field order): `Email[separator]Password[separator]Backup Email[separator]2FA Secret`

```text
# Standard format (using ---- separator)
separator="----"
example1@gmail.com----MyPassword123----backup1@email.com----ABCD1234EFGH5678
example2@gmail.com----P@ssw0rd!%%99----backup2@email.com----WXYZ9012STUV3456

# Email and password only (backup email and 2FA are optional)
example3@gmail.com----ComplexP@ss#2024

# Using pipe separator
separator="|"
example4@gmail.com|AnotherPass!|QRST5678UVWX1234

# Using triple dash
separator="---"
example5@gmail.com---My#Pass@456---helper@email.com---LMNO3456PQRS7890
```

**✅ Important Notes**:
- **Fixed field order**: Email → Password → Backup Email → 2FA Secret
- **Password supports special characters**: `@#$%^&*` etc.
- **Backup email and 2FA are optional**: You can use just email and password
- **Comments**: Lines starting with `#` are ignored
- **One separator per file**: Only one separator type per file

**💡 Recommended Separators**:
- `----` (four dashes) - Recommended, clearest
- `---` (three dashes) - Also works well
- `|` (pipe) - Concise
- `,` (comma) - Note: password cannot contain commas

### 2. `proxies.txt` (Proxy IPs)

Supports Socks5/HTTP, one per line:

```text
socks5://user:pass@host:port
http://user:pass@host:port
```

### 3. `cards.txt` (Virtual Card Info) 🆕

Format: `CardNumber Month Year CVV` (space-separated)

```text
5481087170529907 01 32 536
5481087143137903 01 32 749
```

**Notes**:
- **Card Number**: 13-19 digits
- **Month**: 01-12 (two digits)
- **Year**: Last two digits, e.g., 2032 = 32
- **CVV**: 3-4 digit security code
- One card per line, used for one-click card binding

💳 **Virtual Card Recommendation**: [HolyCard](https://www.holy-card.com/) - Supports Gemini subscription, GPT Team, 0$ Plus, as low as 2R per card

### 4. Output Files (Auto-generated)

* **accounts.db**: SQLite database file (core storage for all account info).
* **sheerIDlink.txt**: Successfully extracted verification links (eligible pending verification with links).
* **eligible_pending.txt**: Eligible accounts without extracted verification links yet.
* **verified_no_card.txt**: Accounts that passed student verification but haven't bound a card.
* **subscribed.txt**: Accounts that completed card binding and subscription.
* **ineligible.txt**: Detected ineligible (unavailable) accounts.
* **error.txt**: Timeout or error accounts.
* **sheerID_verified_success.txt**: Successfully verified SheerID links.
* **sheerID_verified_failed.txt**: Failed verification links with reasons.
* **2fa_codes.txt**: Generated 2FA codes.

### 5. Web Admin Interface

After starting the program, a web server automatically starts in the background (port 8080).

1. Open browser and visit: `http://localhost:8080`
2. View all account statuses, search, filter, and batch export.

## 🤝 Community & Contact

Questions or suggestions? Join our community!

|           💬**Telegram Group**           |    🐧**QQ Group**    |
| :--------------------------------------------: | :-------------------------: |
| [Click to Join](https://t.me/+9zd3YE16NCU3N2Fl) | **QQ Group: 330544197** |
|           ![Telegram QR](Telegram.png)           |       ![QQ QR](QQ.jpg)       |

👤 **Contact Developer**: QQ 2738552008

Donate:
![Donate](zanshang.jpg)

---

## ⚠️ Disclaimer

* This tool is for educational and technical exchange purposes only. Do not use for illegal purposes.
* Please comply with BitBrowser and related platform terms of service.
* The developer is not responsible for any account loss or legal liability arising from use of this tool.

## 📄 License

This project is licensed under the [MIT License](LICENSE).
