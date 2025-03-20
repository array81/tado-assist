# Tado Assist - Home Assistant Integration

![Tado Assist](https://img.shields.io/badge/Tado-Integration-blue.svg)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Compatible-green.svg)
![License](https://img.shields.io/github/license/array81/tado-assist)

## 🚀 Introduction
This integration for **Home Assistant** allows you to use **Tado**'s API to create your own "Auto-Assist." It periodically communicates with Tado's servers to retrieve the home's status and can modify it based on user input.
The integration relies on the PyTado library, which is automatically installed alongside it.

## ✨ Features
- **Automation**: Automates the change of operating mode (Home or Away) and the suspension of home heating.
- **Mobile Device Tracking**: Detect mobile devices linked to Tado and their home presence.
- **Home & Away Modes**: Get your home to "Away" or "Home" mode with ease.
- **Open Window Detection**: Get alerts when a window is detected as open.
- **Customizable Scan Interval**: Choose how frequently the system checks for updates.
- **Data Logging & Debugging**: Includes logging support for easy debugging.

## 🖼 Screenshots
Below are some preview images showcasing Tado Assist in action:

<img src="/assets/images/preview_service.png" width="250">

## 🛠 Installation
### 1️⃣ Install via HACS (Recommended)
1. Open Home Assistant and install [HACS](https://hacs.xyz/).
2. Go to **HACS** → **Integrations** → **Add Custom Repository**.
3. Enter the repository URL: `https://github.com/yourusername/tado-assist`.
4. Click **Install** and restart Home Assistant.
5. Navigate to **Settings** → **Devices & Services** → **Add Integration** → Search for **Tado Assist**.
6. Enter your Tado credentials and configure the scan interval.

### 2️⃣ Manual Installation
1. Download the latest release from [GitHub Releases](https://github.com/array81/tado-assist/releases).
2. Extract the `tado_assist` folder into `config/custom_components/` in your Home Assistant directory.
3. Restart Home Assistant.
4. Add the integration via **Settings** → **Devices & Services**.

## 🤝 Contributing
We welcome contributions! Feel free to open issues, suggest features, or submit pull requests.
- **Feature Requests**: Open an issue describing your idea.
- **Bug Reports**: Report bugs with clear steps to reproduce them.
- **Code Contributions**: Fork the repo, create a new branch, and submit a pull request.
- **Translations**: Translate the integration into your language.

## ☕ Support & Donations
If you find **Tado Assist** useful, consider buying me a coffee to support future development! 

[![ko-fi - Buy me a coffee](https://img.shields.io/badge/ko--fi-Buy_me_a_coffee-FF5A16?logo=ko-fi)](https://ko-fi.com/array81)

## 📜 License
This project is licensed under the [MIT License](LICENSE).

## 📌 Changelog
Stay up to date with the latest changes and improvements:

### v1.0.0 - Initial Release
- First public version.

---
📢 **Stay updated!** Follow the project on GitHub for updates and new features.

