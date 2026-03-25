import cv2
import tkinter as tk
from tkinter import simpledialog, messagebox, ttk, filedialog
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageOps
import os
import sys
import subprocess
import json
import time
import random
import glob
import threading
import queue

import qrcode
import socket

from log import log

def get_local_ip():
    log.info("Getting IP address...")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
        log.error("Failed to obtain private IP address, using 127.0.0.1 for QR generation")
    finally:
        s.close()
    return IP

# ==========================================
# ⚙️ DEFAULT SETTINGS & MEMORY
# ==========================================
SETTINGS_FILE = "photobooth_settings.json"

PAPER_DIMENSIONS = {
    "A4": (3508, 2480) # 300 DPI Landscape
}

SETTINGS = {
    "NUM_PHOTOS": 4, #dont change or it will break lol
    "DISPLAY_SECONDS": 1,           
    "COUNTDOWN_SECONDS": 3,         
    "OVERLAY_IMAGE_PATH": "bottom_right_4k_overlay.png",
    "OVERLAY_SCALE": 1.0,           
    "OVERLAY_X": 0,                 
    "OVERLAY_Y": 0,                 
    "AUTO_PRINT": False,
    "PAPER_SIZE": "A4",      #dont change or it will break lol
    "CAMERA_INDEX": 0,
    "CAMERA_FLASH": True,           
    "CREATE_GIF": True,            
    "GIF_SAVE_PATH": "",            
    "PLAY_SOUNDS": True,            
    "ATTRACT_MODE": True,           
    "ATTRACT_TIME_SECONDS": 60      
}

if os.path.exists(SETTINGS_FILE):
    try:
        with open(SETTINGS_FILE, "r") as f:
            saved_settings = json.load(f)
            for key, value in saved_settings.items():
                SETTINGS[key] = value
            log.ok("Settings loaded successfully!")
    except Exception as e:
        log.error(f"Could not load settings file, using defaults: {e}")
else:
    log.warn("Settings file does not exist, using defaults")


class PhotoBoothApp:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        self.window.geometry("1280x800") 
        self.window.configure(bg="black")
        
        self.is_fullscreen = True  
        self.window.attributes("-fullscreen", self.is_fullscreen)
        self.window.bind("<F11>", self.toggle_fullscreen)
        self.window.bind("<Escape>", self.end_fullscreen)

        self.last_interaction = time.time()
        self.is_attract_mode = False
        self.is_idle_screen = True 
        self.window.bind("<Key>", self.reset_idle_timer)
        self.window.bind("<Button-1>", self.reset_idle_timer)
        
        self.audio_queue = queue.Queue()
        self.audio_thread = threading.Thread(target=self._audio_worker, daemon=True)
        self.audio_thread.start()

        self.current_session_ID = 0
        self.is_single_photo_mode = False # Tracks if we are taking 1 photo or a collage

        try:
            self.comic_font = ImageFont.truetype("comic.ttf", 250)
        except IOError:
            try:
                self.comic_font = ImageFont.truetype("ComicSansMS.ttf", 250)
            except IOError:
                log.warn("Comic Sans not found. Using default.")
                self.comic_font = ImageFont.load_default()

        self.vid = cv2.VideoCapture(SETTINGS["CAMERA_INDEX"], cv2.CAP_DSHOW)
        self.vid.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.vid.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        
        self.photos_taken = []
        self.is_capturing = False
        self.showing_final = False
        self.current_countdown = 0
        self.current_gif = None 
        
        self.btn_frame = tk.Frame(window, bg="black")
        self.btn_frame.pack(side=tk.BOTTOM, pady=15)

        # 🔘 DYNAMIC BUTTON SETUP
        self.start_collage_btn = tk.Button(self.btn_frame, text="📸 Photo Collage", font=("Arial", 16, "bold"), bg="#4CAF50", fg="white", command=self.start_collage_sequence)
        self.start_single_btn = tk.Button(self.btn_frame, text="👤 Single Photo", font=("Arial", 16, "bold"), bg="#9C27B0", fg="white", command=self.start_single_sequence)
        self.settings_btn = tk.Button(self.btn_frame, text="⚙️ Settings", font=("Arial", 16), command=self.open_settings)
        
        self.print_btn = tk.Button(self.btn_frame, text="🖨️ Print It!", font=("Arial", 16, "bold"), bg="#2196F3", fg="white", command=self.print_image)
        self.save_raw_btn = tk.Button(self.btn_frame, text="💾 Save Raw Photos", font=("Arial", 16), command=self.save_raw_photos)
        self.retake_btn = tk.Button(self.btn_frame, text="🗑️ Retake", font=("Arial", 16), bg="#f44336", fg="white", command=self.retake_sequence)
        self.next_btn = tk.Button(self.btn_frame, text="➡️ Next Person", font=("Arial", 16), command=self.reset_to_camera)

        self.canvas = tk.Label(window, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.qr_label = tk.Label(window, bg="white", padx=10, pady=10)

        self.show_idle_ui()
        self.update_webcam()
        self.check_idle_state()

    def reset_idle_timer(self, event=None):
        self.last_interaction = time.time()

    def check_idle_state(self):
        if SETTINGS["ATTRACT_MODE"] and self.is_idle_screen and not self.is_attract_mode:
            if time.time() - self.last_interaction > SETTINGS["ATTRACT_TIME_SECONDS"]:
                self.start_attract_mode()
        
        self.window.after(1000, self.check_idle_state)

    def start_attract_mode(self):
        log.info("Attract mode ON")
        self.is_attract_mode = True
        self.is_idle_screen = False
        
        for widget in self.btn_frame.winfo_children():
            widget.pack_forget()
            
        self.exit_attract_btn = tk.Button(self.btn_frame, text="🔙 Return to Photo Booth", font=("Arial", 20, "bold"), bg="#f44336", fg="white", command=self.stop_attract_mode)
        self.exit_attract_btn.pack(pady=10)
        
        self.play_random_gif()

    def stop_attract_mode(self):
        log.info("Attract mode OFF")
        self.is_attract_mode = False
        self.last_interaction = time.time()
        self.show_idle_ui()

    def play_random_gif(self):
        if not self.is_attract_mode: return
        
        gif_dir = SETTINGS["GIF_SAVE_PATH"] if SETTINGS["GIF_SAVE_PATH"] else os.path.join(os.getcwd(), "GIF_Archive")
        
        if os.path.exists(gif_dir):
            gifs = glob.glob(os.path.join(gif_dir, "*.gif"))
            if gifs:
                chosen_gif = random.choice(gifs)
                try:
                    self.current_gif = Image.open(chosen_gif)
                    self.animate_gif(0)
                    return
                except:
                    pass
        
        img = Image.new('RGB', (1920, 1080), color="black")
        draw = ImageDraw.Draw(img)
        draw.text((400, 500), "Waiting for photos...", font=self.comic_font, fill="white")
        self.display_image(img)
        self.window.after(3000, self.play_random_gif)

    def animate_gif(self, frame_idx):
        """Loops through the frames of the chosen GIF with regulated timing."""
        if not self.is_attract_mode: return
        
        try:
            self.current_gif.seek(frame_idx)
            pil_img = self.current_gif.convert("RGB")
            self.display_image(pil_img)
            
            # --- FIX 1: REGULATE FRAME TIMING ---
            # Safely grab the duration. If it's missing or dangerously low (under 20ms),
            # override it to 100ms (10 fps) to prevent jitter and CPU locking.
            delay = self.current_gif.info.get('duration', 100)
            if not isinstance(delay, int) or delay < 20:
                delay = 100
            
            next_frame = frame_idx + 1
            if next_frame >= self.current_gif.n_frames:
                # --- FIX 2: CONSISTENT TRANSITION TIME ---
                # Hold the very last frame for 2000ms (2 seconds) before loading the next GIF
                # You can adjust this number to make the gap shorter or longer!
                self.window.after(500, self.play_random_gif) 
            else:
                self.window.after(delay, lambda: self.animate_gif(next_frame))
                
        except Exception as e:
            log.error(f"GIF Playback Error at frame {frame_idx}: {e}")
            # If a GIF is fundamentally broken, wait 1 second and load a new one
            self.window.after(1000, self.play_random_gif)

    def play_sound(self, sound_type):
        if not SETTINGS["PLAY_SOUNDS"]: return
        self.audio_queue.put(sound_type)

    def show_idle_ui(self):
        self.is_idle_screen = True
        self.last_interaction = time.time()
        for widget in self.btn_frame.winfo_children():
            widget.pack_forget()
            
        if hasattr(self, 'qr_label'):
            self.qr_label.place_forget() 
            
        self.start_collage_btn.pack(side=tk.LEFT, padx=10)
        self.start_single_btn.pack(side=tk.LEFT, padx=10)
        self.settings_btn.pack(side=tk.LEFT, padx=10)

    def show_finished_ui(self):
        self.is_idle_screen = False
        for widget in self.btn_frame.winfo_children():
            widget.pack_forget()
        self.print_btn.pack(side=tk.LEFT, padx=10)
        self.save_raw_btn.pack(side=tk.LEFT, padx=10)
        self.retake_btn.pack(side=tk.LEFT, padx=10)
        self.next_btn.pack(side=tk.LEFT, padx=10)

    def crop_to_16_9(self, frame):
        h, w = frame.shape[:2]
        if abs((w / h) - (16 / 9)) < 0.05:
            return frame
        target_w = int(h * 16 / 9)
        if target_w <= w:
            start_x = (w - target_w) // 2
            return frame[:, start_x:start_x+target_w]
        else:
            target_h = int(w * 9 / 16)
            start_y = (h - target_h) // 2
            return frame[start_y:start_y+target_h, :]

    def update_webcam(self):
        ret, frame = self.vid.read()
        
        if ret and not self.is_capturing and not self.showing_final and not self.is_attract_mode:
            frame = self.crop_to_16_9(frame)
            cv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img_original = Image.fromarray(cv_img)
            
            # Flip image horizontally ONLY for the screen preview (mirror effect)
            pil_img_display = pil_img_original.transpose(Image.FLIP_LEFT_RIGHT)
            
            if self.current_countdown > 0:
                draw = ImageDraw.Draw(pil_img_display)
                text = str(self.current_countdown)
                draw.text((50, 20), text, font=self.comic_font, fill="white", stroke_width=8, stroke_fill="black")
            
            self.display_image(pil_img_display)
        
        self.window.after(15, self.update_webcam)

    def display_image(self, pil_img):
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w < 100 or canvas_h < 100:
            canvas_w, canvas_h = 1280, 720
            
        if self.is_attract_mode:
            # Force the GIF/Attract slide to fill the entire UI canvas
            pil_img_resized = ImageOps.fit(pil_img, (canvas_w, canvas_h), method=Image.Resampling.LANCZOS)
        else:
            # Normal scaling that respects aspect ratio bounds
            pil_img_resized = pil_img.copy()
            pil_img_resized.thumbnail((canvas_w, canvas_h), Image.Resampling.LANCZOS)
            
        self.photo = ImageTk.PhotoImage(image=pil_img_resized)
        self.canvas.configure(image=self.photo)

    def start_collage_sequence(self):
        log.info("Starting Collage Sequence")
        self.is_single_photo_mode = False
        self._init_sequence()

    def start_single_sequence(self):
        log.info("Starting Single Photo Sequence")
        self.is_single_photo_mode = True
        self._init_sequence()

    def _init_sequence(self):
        self.current_session_ID = int(time.time()) 
        self.is_idle_screen = False 
        for widget in self.btn_frame.winfo_children():
            widget.pack_forget()
        self.photos_taken = []
        self.showing_final = False
        self.take_next_photo()

    def retake_sequence(self):
        log.info("Retaking sequence")
        self.reset_to_camera()
        if self.is_single_photo_mode:
            self.start_single_sequence()
        else:
            self.start_collage_sequence()

    def take_next_photo(self):
        target_photos = 1 if self.is_single_photo_mode else SETTINGS["NUM_PHOTOS"]
        if len(self.photos_taken) < target_photos:
            self.run_countdown(SETTINGS["COUNTDOWN_SECONDS"])
        else:
            if self.is_single_photo_mode:
                self.generate_single_photo_layout()
            else:
                self.generate_collage()

    def run_countdown(self, count):
        self.current_countdown = count
        if count > 0:
            self.play_sound("beep") 
            self.window.after(1000, self.run_countdown, count - 1)
        else:
            self.snap_photo()

    def trigger_flash(self, duration=40):
        flash = tk.Frame(self.window, bg="white")
        flash.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.window.update() 
        self.window.after(duration, flash.destroy)

    def snap_photo(self):
        self.is_capturing = True
        self.play_sound("snap") 
        
        if SETTINGS["CAMERA_FLASH"]:
            self.trigger_flash(40) 
            self.window.after(100, lambda: self.trigger_flash(40)) 

        ret, frame = self.vid.read()
        if ret:
            frame = self.crop_to_16_9(frame)
            cv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img_original = Image.fromarray(cv_img)
            
            # Save the UNFLIPPED image so the text/reality is correct
            self.photos_taken.append(pil_img_original)
            
            # Briefly show the mirrored version so the user doesn't get disoriented
            pil_img_display = pil_img_original.transpose(Image.FLIP_LEFT_RIGHT)
            self.display_image(pil_img_display) 
            
            self.window.after(SETTINGS["DISPLAY_SECONDS"] * 1000, self.resume_camera_and_next)

    def resume_camera_and_next(self):
        self.is_capturing = False
        self.window.after(100, self.take_next_photo)

    def apply_overlay(self, image_canvas):
        """Helper to apply overlay to any final layout"""
        overlay_path = SETTINGS["OVERLAY_IMAGE_PATH"]
        if os.path.exists(overlay_path):
            try:
                overlay = Image.open(overlay_path).convert("RGBA")
                new_w = int(overlay.width * SETTINGS["OVERLAY_SCALE"])
                new_h = int(overlay.height * SETTINGS["OVERLAY_SCALE"])
                overlay = overlay.resize((new_w, new_h), Image.Resampling.LANCZOS)
                image_canvas.paste(overlay, (SETTINGS["OVERLAY_X"], SETTINGS["OVERLAY_Y"]), overlay)
            except Exception as e:
                log.warn(f"Failed to load overlay: {e}")
        return image_canvas

    def generate_single_photo_layout(self):
        log.info("Generating Single Photo Layout (Fill)")
        self.showing_final = True

        # To this:
        canvas_w, canvas_h = PAPER_DIMENSIONS.get(SETTINGS["PAPER_SIZE"], (3508, 2480))
        
        # ImageOps.fit scales and crops the image to completely FILL the target dimensions
        final_layout = ImageOps.fit(
            self.photos_taken[0], 
            (canvas_w, canvas_h), 
            method=Image.Resampling.LANCZOS
        )
        
        final_layout = self.apply_overlay(final_layout)
        self.finalize_sequence(final_layout)

    def generate_collage(self):
        self.showing_final = True
        canvas_w, canvas_h = 3840, 2160
        collage = Image.new('RGB', (canvas_w, canvas_h), color="white")
        quad_w, quad_h = 1920, 1080
        positions = [(0, 0), (quad_w, 0), (0, quad_h), (quad_w, quad_h)]
        
        for i, img in enumerate(self.photos_taken):
            resized = img.resize((quad_w, quad_h), Image.Resampling.LANCZOS)
            collage.paste(resized, positions[i])
            
        overlay_path = SETTINGS["OVERLAY_IMAGE_PATH"]
        if os.path.exists(overlay_path):
            try:
                overlay = Image.open(overlay_path).convert("RGBA")
                new_w = int(overlay.width * SETTINGS["OVERLAY_SCALE"])
                new_h = int(overlay.height * SETTINGS["OVERLAY_SCALE"])
                overlay = overlay.resize((new_w, new_h), Image.Resampling.LANCZOS)
                collage.paste(overlay, (SETTINGS["OVERLAY_X"], SETTINGS["OVERLAY_Y"]), overlay)
            except Exception as e:
                log.warn(f"Failed to load overlay: {e}")
            
        # ... (top part of generate_collage stays the same) ...
        
        self.final_collage_path = "final_collage_4k.jpg"
        collage.save(self.final_collage_path, quality=95)
        self.display_image(collage)
        
        self.show_finished_ui()
        self.window.update() 
        
        # 1. Silently auto-save raw photos so the web server has files to serve
        self.save_raw_photos(silent=True) 
        
        # 2. Generate the GIF if enabled
        if SETTINGS["CREATE_GIF"]:
            self.generate_gif()
            
        # 3. Generate and Display the QR Code in the bottom right corner!
        self.display_qr_code()
        if hasattr(self, 'qr_label'):
            # This floats the QR code nicely in the bottom right corner over the canvas
            self.qr_label.place(relx=0.98, rely=0.85, anchor="se")
            
        # 4. Auto Print if enabled
        if SETTINGS["AUTO_PRINT"]:
            self.print_image()
                
        self.final_collage_path = "final_collage_4k.jpg"
        collage.save(self.final_collage_path, quality=95)
        self.display_image(collage)
        
        self.show_finished_ui()
        self.window.update() # Force UI to draw before processing prints/gifs
        
        if SETTINGS["CREATE_GIF"]:
            self.generate_gif()
        if SETTINGS["AUTO_PRINT"]:
            self.print_image()

    def finalize_sequence(self, final_image):
        """Unified method to save archives, display UI, and print"""
        self.final_collage_path = "final_output.jpg"
        final_image.save(self.final_collage_path, quality=95)
        
        # Save to Archive folder
        self.save_final_to_archive(final_image)

        # Do NOT mirror the final output on the screen. Show it exactly as printed.
        self.display_image(final_image)
        self.show_finished_ui()
        self.window.update() 
        
        self.save_raw_photos(silent=True) 
        if SETTINGS["CREATE_GIF"]: self.generate_gif()
            
        self.display_qr_code()
        if hasattr(self, 'qr_label'):
            self.qr_label.place(relx=0.98, rely=0.85, anchor="se")
            
        if SETTINGS["AUTO_PRINT"]:
            self.print_image()

    def save_final_to_archive(self, final_image):
        try:
            base_dir = os.path.join(os.getcwd(), "Final_Archive")
            save_dir = os.path.join(base_dir, f"Session_{self.current_session_ID}")
            os.makedirs(save_dir, exist_ok=True)
            archive_path = os.path.join(save_dir, "final_print.jpg")
            final_image.save(archive_path, quality=95)
            log.ok(f"Final output archived to: {archive_path[-40:]}")
        except Exception as e:
            log.error(f"Failed to archive final image: {e}")

    def generate_gif(self):
        try:
            gif_dir = SETTINGS["GIF_SAVE_PATH"]
            if not gif_dir or not os.path.exists(gif_dir):
                gif_dir = os.path.join(os.getcwd(), "GIF_Archive")
                os.makedirs(gif_dir, exist_ok=True)
            
            gif_frames = [img.resize((800, 450), Image.Resampling.LANCZOS) for img in self.photos_taken]
            gif_path = os.path.join(gif_dir, f"booth_{self.current_session_ID}.gif")
            
            gif_frames[0].save(gif_path, save_all=True, append_images=gif_frames[1:], duration=500, loop=0)
            log.ok(f"Animated GIF saved to: {gif_path[-33:]}")
        except Exception as e:
            log.error(f"Failed to generate GIF: {e}")

    def save_raw_photos(self, silent=False):
        self.reset_idle_timer()
        if not self.photos_taken: return
        
        base_dir = os.path.join(os.getcwd(), "Raw_Archive")
        save_dir = os.path.join(base_dir, f"Session_{self.current_session_ID}")
        os.makedirs(save_dir, exist_ok=True)
        
        for i, img in enumerate(self.photos_taken):
            img.save(os.path.join(save_dir, f"shot_{i+1}.jpg"), quality=100)
            
        if not silent:
            messagebox.showinfo("Success", f"Raw photos saved to:\n{save_dir}")
        log.ok(f"Raw photos saved to: {save_dir[-33:]}")

    def reset_to_camera(self):
        self.showing_final = False
        self.show_idle_ui()

    def open_settings(self):
        win = tk.Toplevel(self.window)
        win.title("Settings")
        win.geometry("450x750") 
        
        tk.Label(win, text="Select Camera:").pack(pady=2)
        cam_var = tk.StringVar(value=f"Camera {SETTINGS['CAMERA_INDEX']}")
        cam_dropdown = ttk.Combobox(win, textvariable=cam_var, state="readonly")
        cam_dropdown['values'] = ("Camera 0", "Camera 1", "Camera 2", "Camera 3", "Camera 4")
        cam_dropdown.pack()
        
        tk.Label(win, text="Display Seconds:").pack(pady=2)
        disp_var = tk.StringVar(value=str(SETTINGS["DISPLAY_SECONDS"]))
        tk.Entry(win, textvariable=disp_var).pack()
        
        tk.Label(win, text="Countdown Seconds:").pack(pady=2)
        count_var = tk.StringVar(value=str(SETTINGS["COUNTDOWN_SECONDS"]))
        tk.Entry(win, textvariable=count_var).pack()
        
        tk.Label(win, text="Overlay Image Path:").pack(pady=2)
        over_var = tk.StringVar(value=SETTINGS["OVERLAY_IMAGE_PATH"])
        tk.Entry(win, textvariable=over_var).pack()
        
        tk.Label(win, text="Overlay Scale (1.0 = 100%):").pack(pady=2)
        scale_var = tk.StringVar(value=str(SETTINGS["OVERLAY_SCALE"]))
        tk.Entry(win, textvariable=scale_var).pack()
        
        tk.Label(win, text="Overlay X / Y Offset:").pack(pady=2)
        xy_frame = tk.Frame(win)
        xy_frame.pack()
        x_var = tk.StringVar(value=str(SETTINGS["OVERLAY_X"]))
        y_var = tk.StringVar(value=str(SETTINGS["OVERLAY_Y"]))
        tk.Entry(xy_frame, textvariable=x_var, width=10).pack(side=tk.LEFT, padx=2)
        tk.Entry(xy_frame, textvariable=y_var, width=10).pack(side=tk.LEFT, padx=2)
        
        tk.Label(win, text="--- Special Features ---").pack(pady=(10, 2))
        
        sound_var = tk.BooleanVar(value=SETTINGS["PLAY_SOUNDS"])
        tk.Checkbutton(win, text="🔊 Play Beeps & Snap Sounds", variable=sound_var).pack()

        flash_var = tk.BooleanVar(value=SETTINGS["CAMERA_FLASH"])
        tk.Checkbutton(win, text="📸 Enable Double Flash Effect", variable=flash_var).pack()
        
        auto_print_var = tk.BooleanVar(value=SETTINGS["AUTO_PRINT"])
        tk.Checkbutton(win, text="🖨️ Auto Print Output", variable=auto_print_var).pack()

        gif_var = tk.BooleanVar(value=SETTINGS["CREATE_GIF"])
        tk.Checkbutton(win, text="🎞️ Generate Looping GIF", variable=gif_var).pack()
        
        gif_frame = tk.Frame(win)
        gif_frame.pack()
        gif_path_var = tk.StringVar(value=SETTINGS["GIF_SAVE_PATH"])
        tk.Entry(gif_frame, textvariable=gif_path_var, width=30).pack(side=tk.LEFT)
        def browse_dir():
            d = filedialog.askdirectory()
            if d: gif_path_var.set(d)
        tk.Button(gif_frame, text="Browse", command=browse_dir).pack(side=tk.LEFT, padx=5)
        
        tk.Label(win, text="--- Attract Mode ---").pack(pady=(10, 2))
        attract_var = tk.BooleanVar(value=SETTINGS["ATTRACT_MODE"])
        tk.Checkbutton(win, text="📺 Play GIFs when Idle", variable=attract_var).pack()
        
        idle_frame = tk.Frame(win)
        idle_frame.pack()
        tk.Label(idle_frame, text="Trigger after idle seconds:").pack(side=tk.LEFT)
        idle_var = tk.StringVar(value=str(SETTINGS["ATTRACT_TIME_SECONDS"]))
        tk.Entry(idle_frame, textvariable=idle_var, width=5).pack(side=tk.LEFT, padx=5)

        def save_settings():
            try:
                old_cam_index = SETTINGS["CAMERA_INDEX"]
                new_cam_index = int(cam_var.get().replace("Camera ", ""))
                
                SETTINGS["CAMERA_INDEX"] = new_cam_index
                SETTINGS["DISPLAY_SECONDS"] = int(disp_var.get())
                SETTINGS["COUNTDOWN_SECONDS"] = int(count_var.get())
                SETTINGS["OVERLAY_IMAGE_PATH"] = over_var.get()
                SETTINGS["OVERLAY_SCALE"] = float(scale_var.get())
                SETTINGS["OVERLAY_X"] = int(x_var.get())
                SETTINGS["OVERLAY_Y"] = int(y_var.get())
                SETTINGS["AUTO_PRINT"] = auto_print_var.get()
                SETTINGS["CAMERA_FLASH"] = flash_var.get()
                SETTINGS["CREATE_GIF"] = gif_var.get()
                SETTINGS["GIF_SAVE_PATH"] = gif_path_var.get()
                SETTINGS["PLAY_SOUNDS"] = sound_var.get()
                SETTINGS["ATTRACT_MODE"] = attract_var.get()
                SETTINGS["ATTRACT_TIME_SECONDS"] = int(idle_var.get())
                
                with open(SETTINGS_FILE, "w") as f:
                    json.dump(SETTINGS, f, indent=4)
                
                if old_cam_index != SETTINGS["CAMERA_INDEX"]:
                    self.vid.release()
                    self.vid = cv2.VideoCapture(SETTINGS["CAMERA_INDEX"], cv2.CAP_DSHOW)
                    self.vid.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                    self.vid.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                    
                win.destroy()
                log.ok("Settings saved successfully.")
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numbers.")
                
        tk.Button(win, text="Save Settings", font=("Arial", 12, "bold"), command=save_settings).pack(pady=15)

    def print_image(self):
        log.info("Sending image to printer")
        self.reset_idle_timer()
        if not hasattr(self, 'final_collage_path'): return
        
        popup = tk.Label(self.window, text="🖨️ Sending to Printer...", font=("Arial", 45, "bold"), bg="white", fg="black", padx=40, pady=30, relief="solid", bd=5)
        popup.place(relx=0.5, rely=0.5, anchor="center")
        self.window.update() 
        
        if sys.platform == "win32":
            try:
                import win32print
                import win32ui
                from PIL import ImageWin
                
                printer_name = win32print.GetDefaultPrinter()
                hDC = win32ui.CreateDC()
                hDC.CreatePrinterDC(printer_name)
                
                horzres = hDC.GetDeviceCaps(8)  
                vertres = hDC.GetDeviceCaps(10) 
                
                img = Image.open(self.final_collage_path)
                if horzres < vertres and img.size[0] > img.size[1]:
                    img = img.rotate(90, expand=True)
                    
                ratio = min(horzres / img.size[0], vertres / img.size[1])
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                x = (horzres - new_size[0]) // 2
                y = (vertres - new_size[1]) // 2
                
                img_resized = img.resize(new_size, Image.Resampling.LANCZOS)
                
                hDC.StartDoc("PhotoBooth Print")
                hDC.StartPage()
                dib = ImageWin.Dib(img_resized)
                dib.draw(hDC.GetHandleOutput(), (x, y, x + new_size[0], y + new_size[1]))
                hDC.EndPage()
                hDC.EndDoc()
                hDC.DeleteDC()
                log.ok("Print command sent successfully on Windows.")
            except Exception as e:
                messagebox.showerror("Print Error", f"Failed to print: {e}")
                log.error("Print Error " + f"Failed to print: {e}")
        else:
            try:
                subprocess.run(["lp" if sys.platform != "darwin" else "lpr", self.final_collage_path])
                log.ok("Print command sent successfully on Unix/macOS.")
            except Exception as e:
                log.error(f"Failed to execute print command: {e}")

        self.window.after(3000, popup.destroy)

    def _audio_worker(self):
        if sys.platform == "win32":
            try:
                import winsound
            except ImportError:
                winsound = None
        else:
            winsound = None

        while True:
            sound_type = self.audio_queue.get()
            if winsound and SETTINGS["PLAY_SOUNDS"]:
                try:
                    if sound_type == "beep":
                        winsound.Beep(800, 200) 
                    elif sound_type == "snap":
                        winsound.Beep(2000, 100) 
                except Exception as e:
                    log.error(f"Audio playback failed: {e}")
            self.audio_queue.task_done()

    def display_qr_code(self):
        local_ip = get_local_ip()
        session_url = f"http://{local_ip}/session/{self.current_session_ID}"
        log.info(f"Session URL generated: {session_url}")
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(session_url)
        qr.make(fit=True)
        
        qr_pil_image = qr.make_image(fill_color="black", back_color="white")
        qr_pil_image = qr_pil_image.resize((300, 300), Image.Resampling.LANCZOS)
        
        self.qr_tk_image = ImageTk.PhotoImage(qr_pil_image)
        
        if hasattr(self, 'qr_label'):
            self.qr_label.config(image=self.qr_tk_image)
            self.qr_label.image = self.qr_tk_image

    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.window.attributes("-fullscreen", self.is_fullscreen)

    def end_fullscreen(self, event=None):
        self.is_fullscreen = False
        self.window.attributes("-fullscreen", False)

    def on_closing(self):
        log.info("Shutting down Photo Booth application")
        self.vid.release()
        self.window.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoBoothApp(root, "Python Photo Booth")
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()