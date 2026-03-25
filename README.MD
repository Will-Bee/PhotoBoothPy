# Interactive Python PhotoBooth

A streamlined, touch-optimized PhotoBooth solution that captures photos, generates GIFs, and allows users to download their media via a local network QR code.

---

## 🏗️ System Architecture

The application operates using two primary Python scripts running simultaneously:

1.  **`main.py`**: The core PhotoBooth interface. It handles the camera feed, countdowns, image processing, and QR code generation.
2.  **`web.py`**: A lightweight Flask server that hosts the captured media on your local network for instant user downloads.
2.  **`log.py`**: Custom script for logging in nice format


---

## 🔌 Hardware Requirements

* **Camera:** * **Recommended:** A professional DSLR/Mirrorless camera connected via HDMI to a **Capture Card**. Route this through **OBS Studio** and use the **OBS Virtual Camera** for the best image quality. [See this guide to enable virtual camera in OBS](https://obsproject.com/kb/virtual-camera-troubleshooting)
    * **Minimum:** Any standard USB webcam or integrated system camera.
* **Printer:** * Uses the **Windows Default Printer**. If no printer is connected, the system will default to "Print to PDF."
* **Display:** * Optimized for **Touch Screen** interaction.

---

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have Python installed, then install the necessary dependencies:

```bash
pip install opencv-python pillow qrcode[pil] flask
```

### 2. Configuration
* Set your desired printer as the **Default Printer** in Windows.
* If using a professional camera, start your **OBS Virtual Camera** before launching the app.

* In the app itself, there are settings regarding countdown, for how long you want to display each photo after capturing, sound and visual effects and more.

### 3. Running the App
The simplest way to start the entire ecosystem is via the provided batch file:

1.  Double-click **`PhotoBoothAppStartup.bat`**.
2.  This will automatically launch both the web server and the main UI.

---

## 🛠️ How it Works

* **Capture:** The user interacts with the touch-friendly UI to start a session.
* **Processing:** The script captures multiple frames, saves them, and compiles a colage and GIF.
* **Printing:** One-click funtionality for printing the photo, right during the event.
* **Sharing:** A unique QR code is displayed on the screen after each session.
* **Download:** When the user scans the QR code with their phone (connected to the same local Wi-Fi), they are directed to the local `web.py` landing page to download their files.



---

