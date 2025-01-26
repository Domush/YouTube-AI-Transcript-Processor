# Standard library imports
import builtins
from datetime import datetime
import json, os
import threading
import queue

# Third-party imports
import tkinter as tk
from tkinter import ttk, filedialog
from ttkthemes import ThemedTk
from tkinter import font as tkfont

# Local imports
from AiTranscriptProcessor import AiTranscriptProcessor


# YouTube Transcriber GUI
class TranscriptProcessorGUI(tk.Frame):
    """GUI interface for the transcript processor"""

    def __init__(self, master=None):
        # Basic initialization
        super().__init__(master)
        self.master = master
        self.current_path = os.getcwd()

        # Save original print function
        self.original_print = builtins.print

        # Core components initialization
        self.processor = AiTranscriptProcessor()
        self.selected_paths = []
        self.is_directory = False
        self.selection_frame = None
        self.include_subdirs_var = tk.BooleanVar(value=False)

        # Processing thread components
        self.processing_queue = queue.Queue()
        self.processing_thread = None
        self.processing_cancelled = False

        # Window setup and positioning
        self.master.minsize(800, 600)
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        window_width = max(768, min(screen_width - 100, 1200))
        window_height = max(600, screen_height // 2)
        self.master.geometry(f"{window_width}x{window_height}")

        # Add binding storage
        self.bindings = {}

        # Define standard fonts
        self.fonts = {
            "default": ("Segoe UI", 10),
            "title": ("Segoe UI", 12, "bold"),
            "header": ("Segoe UI", 11),
            "monospace": ("Consolas", 10),
        }

        # GUI initialization
        self.setup_gui()

        # Center window
        self.master.update_idletasks()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.master.geometry(f"+{x}+{y}")

        # Window close handler
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Setup output redirection
        self.setup_output_redirection()

        print("Transcript Processor ready", type="info")

    def setup_gui(self):
        """Initialize all GUI components"""
        # Configure main window
        self.master.title("YouTube Transcript Processor")

        # Configure custom styles
        style = ttk.Style()
        fg_color = style.lookup("TLabel", "foreground") or "black"

        # Configure default font and colors
        style.configure(".", font=self.fonts["default"], foreground=fg_color)
        style.configure("Title.TLabel", font=self.fonts["title"])
        style.configure("Header.TLabel", font=self.fonts["header"])
        style.configure("TCombobox", foreground=fg_color)
        style.map(
            "TCombobox",
            fieldforeground=[("readonly", fg_color)],
            selectforeground=[("readonly", fg_color)],
        )

        # Configure custom button styles
        style.configure(
            "Action.TButton", padding=10, font=self.fonts["default"], width=15
        )
        style.configure(
            "Begin.TButton",
            background="#e8ffe8",
            padding=10,
            font=self.fonts["default"],
            width=20,
        )
        style.configure(
            "Cancel.TButton",
            background="#ffe8e8",
            padding=10,
            font=self.fonts["default"],
            width=20,
        )

        # Create main frame with padding
        self.main_frame = ttk.Frame(self.master, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Add title
        title_label = ttk.Label(
            self.main_frame, text="YouTube Transcript Processor", style="Title.TLabel"
        )
        title_label.pack(pady=(0, 20))

        # Provider selection with improved layout
        self.provider_frame = ttk.LabelFrame(
            self.main_frame, text="AI Provider", padding="10"
        )
        self.provider_frame.pack(fill=tk.X, pady=(0, 15))

        # Get current ttk style colors for consistency
        style = ttk.Style()
        fg_color = style.lookup("TLabel", "foreground") or "black"
        bg_color = style.lookup("TFrame", "background") or "white"

        self.provider_var = tk.StringVar()
        self.provider_combo = ttk.Combobox(
            self.provider_frame,
            textvariable=self.provider_var,
            state="readonly",
            font=self.fonts["default"],
            foreground=fg_color,  # Match the theme's text color
        )
        self.provider_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.set_default_btn = ttk.Button(
            self.provider_frame,
            text="Set as Default",
            command=self.set_default_provider,
            style="Action.TButton",
        )
        self.set_default_btn.pack(side=tk.LEFT, padx=5)

        # Prevent text selection when changing values
        def on_select(event):
            self.provider_combo.selection_clear()

        self.provider_combo.bind("<<ComboboxSelected>>", on_select)

        # Process buttons in their own styled frame
        self.process_frame = ttk.Frame(self.main_frame)
        self.process_frame.pack(fill=tk.X, pady=(0, 15))

        self.process_file_btn = ttk.Button(
            self.process_frame,
            text="Select File(s)",
            command=self.select_files,
            style="Action.TButton",
        )
        self.process_file_btn.pack(side=tk.LEFT, padx=5)

        self.process_dir_btn = ttk.Button(
            self.process_frame,
            text="Select Directory",
            command=self.select_directory,
            style="Action.TButton",
        )
        self.process_dir_btn.pack(side=tk.LEFT, padx=5)

        # Progress section with header
        progress_header = ttk.Label(
            self.main_frame, text="Progress", style="Header.TLabel"
        )
        progress_header.pack(fill=tk.X, pady=(0, 5))

        # Add progress bar
        self.progress_var = tk.StringVar(value="Ready")
        self.progress_label = ttk.Label(self.main_frame, textvariable=self.progress_var)
        self.progress_label.pack(fill=tk.X, pady=(0, 5))

        self.progress_bar = ttk.Progressbar(self.main_frame, mode="indeterminate")
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))

        # Status log with header and improved visuals
        log_header = ttk.Label(
            self.main_frame, text="Status Log", style="Header.TLabel"
        )
        log_header.pack(fill=tk.X, pady=(15, 5))

        self.log_frame = ttk.Frame(self.main_frame, padding="2")
        self.log_frame.pack(fill=tk.BOTH, expand=True)

        # Create styled log text widget with custom font and pack it
        self.log_text = tk.Text(
            self.log_frame,
            height=10,
            wrap=tk.WORD,
            font=self.fonts["monospace"],
            relief="flat",
            padx=10,
            pady=10,
        )
        self.log_text.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True
        )  # Make sure text widget is packed properly

        # Get theme colors
        fg_color = style.lookup("TLabel", "foreground") or "black"

        # Configure default text color for non-tagged text
        self.log_text.configure(foreground="black")  # Add default text color

        # Configure status tags with improved colors
        self.log_text.tag_configure("log", foreground="black")  # Add default tag color
        self.log_text.tag_configure("info", foreground="#2E86C1")  # Softer blue
        self.log_text.tag_configure("warning", foreground="#E67E22")  # Softer orange
        self.log_text.tag_configure("error", foreground="#E74C3C")  # Softer red
        self.log_text.tag_configure("success", foreground="#27AE60")  # Softer green

        # Add scrollbar
        log_scrollbar = ttk.Scrollbar(
            self.log_frame, orient=tk.VERTICAL, command=self.log_text.yview
        )
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

        # Initialize provider list
        self.load_providers()

        # Add tooltip for process file button
        self._create_tooltip(
            self.process_file_btn, "Select one or more JSON files to process (Ctrl+O)"
        )

        # Add tooltip for process directory button
        self._create_tooltip(
            self.process_dir_btn,
            "Select a directory containing JSON files (Ctrl+D)\n\nIf 'Include Subdirectories' is checked, all subdirectories will be processed as well",
        )

        # Add keyboard shortcuts with stored binding IDs
        self.bind_shortcuts()

    def bind_shortcuts(self):
        """Setup keyboard shortcuts with stored binding IDs"""
        self.bindings["file"] = self.master.bind(
            "<Control-o>", lambda e: self.select_files()
        )
        self.bindings["dir"] = self.master.bind(
            "<Control-d>", lambda e: self.select_directory()
        )
        self.bindings["begin"] = None  # Will be set when begin button is created

    def _create_tooltip(self, widget, text):
        """Create a tooltip for a given widget."""

        def enter(event):
            x, y, _, _ = widget.bbox("insert")
            x += widget.winfo_rootx() + 45
            y += widget.winfo_rooty() + 40

            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x}+{y}")

            label = ttk.Label(
                tip,
                text=text,
                justify=tk.LEFT,
                background="#ffffe0",
                relief=tk.SOLID,
                borderwidth=1,
                padding="5",
            )
            label.pack()
            widget.tooltip = tip

        def leave(event):
            if hasattr(widget, "tooltip"):
                widget.tooltip.destroy()
                del widget.tooltip

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def load_providers(self):
        try:
            with open(".api-keys.json", "r") as f:
                api_keys = json.load(f)
                self.providers = {
                    key: value
                    for key, value in api_keys["ai-providers"].items()
                    if key != "default"
                }
                # Create mapping of display names to provider keys
                self.provider_name_to_key = {
                    value["name"]: key for key, value in self.providers.items()
                }
                provider_names = list(self.provider_name_to_key.keys())
                default_provider = (
                    api_keys["ai-providers"].get("default", {}).get("name")
                )
                self.provider_combo["values"] = provider_names
                if default_provider:
                    self.provider_combo.set(default_provider)
                else:
                    self.provider_combo.set("")
        except Exception as e:
            self.log_message(f"Error loading providers: {e}", "error")

    def set_default_provider(self):
        selected_name = self.provider_var.get()
        if selected_name:
            try:
                # Find the provider key by matching the name
                selected_key = next(
                    (
                        key
                        for key, value in self.providers.items()
                        if value["name"] == selected_name
                    ),
                    None,
                )
                if not selected_key:
                    self.log_message(f"Provider {selected_name} not found", "error")
                    return

                with open(".api-keys.json", "r+") as f:
                    api_keys = json.load(f)
                    api_keys["ai-providers"]["default"] = api_keys["ai-providers"][
                        selected_key
                    ]
                    f.seek(0)
                    json.dump(api_keys, f, indent=4)
                    f.truncate()
                self.log_message(f"Set {selected_name} as default provider", "success")
            except Exception as e:
                self.log_message(f"Error setting default: {e}", "error")

    def select_files(self):
        """Handle file selection"""
        files = filedialog.askopenfilenames(
            initialdir=self.current_path,
            title="Select JSON file(s) to process",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if files:
            self.selected_paths = files
            self.is_directory = False
            self.update_selection_display()

    def select_directory(self):
        """Handle directory selection"""
        directory = filedialog.askdirectory(
            initialdir=self.current_path,
            title="Select Directory to Process",
        )
        if directory:
            self.selected_paths = [directory]
            self.is_directory = True
            self.update_selection_display()

    def update_selection_display(self):
        """Update the selection display area with current selection"""
        if self.selection_frame is not None:
            self.selection_frame.destroy()

        if not self.selected_paths:
            self.selection_frame = None
            return

        # Create new selection frame
        self.selection_frame = ttk.LabelFrame(
            self.main_frame, text="Selection", padding="5"
        )
        self.selection_frame.pack(fill=tk.X, pady=5, after=self.process_frame)

        # Calculate required height based on content
        if self.is_directory:
            num_lines = 1  # Directory path
        else:
            num_lines = len(self.selected_paths)  # One line per file

        # Set minimum height of 1 line and maximum of 10 lines
        display_height = min(max(1, num_lines), 10)

        # Create frame for selection text with scrollbar
        selection_text_frame = ttk.Frame(self.selection_frame)
        selection_text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Get theme colors
        style = ttk.Style()
        fg_color = style.lookup("TLabel", "foreground") or "black"

        # Style the selection display
        selection_text = tk.Text(
            selection_text_frame,
            height=display_height,
            wrap=tk.NONE,
            font=self.fonts["default"],
            relief="flat",
            padx=10,
            pady=5,
            background="#F8F9FA",  # Light gray background
            foreground=fg_color,  # Match the theme's text color
            borderwidth=0,
            takefocus=0,  # Prevent focus
            cursor="arrow",  # Use normal cursor instead of text cursor
        )
        selection_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Only show scrollbar if content exceeds display height
        selection_scrollbar = ttk.Scrollbar(
            selection_text_frame, orient=tk.VERTICAL, command=selection_text.yview
        )
        if num_lines > 10:  # Show scrollbar only if needed
            selection_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        selection_text.configure(yscrollcommand=selection_scrollbar.set)

        # Add begin button with a regular tk Frame for background color
        begin_frame = tk.Frame(  # Change from ttk.Frame to tk.Frame
            self.selection_frame, background="#e8ffe8"
        )
        begin_frame.pack(side=tk.RIGHT, padx=10, pady=5)

        self.begin_btn = ttk.Button(
            begin_frame,
            text="Begin Processing",
            command=self.begin_processing,
            style="Begin.TButton",
        )
        self.begin_btn.pack(expand=True, padx=1, pady=1)

        # Add tooltip for begin button and bind shortcut
        self._create_tooltip(self.begin_btn, "Start processing selected files (Ctrl+B)")
        self.bindings["begin"] = self.master.bind(
            "<Control-b>", lambda e: self.begin_processing()
        )

        # Add content
        if self.is_directory:
            directory = self.selected_paths[0]
            selection_text.insert(tk.END, f"Directory: {directory}")
            self.include_subdirs_cb = ttk.Checkbutton(
                self.selection_frame,
                text="Include Subdirectories",
                variable=self.include_subdirs_var,
            )
            self.include_subdirs_cb.pack(side=tk.LEFT, padx=5)
        else:
            for path in self.selected_paths:
                filename = os.path.basename(path)
                selection_text.insert(tk.END, f"• {filename}\n")

        # Make text widget read-only and disable interaction
        selection_text.configure(state="disabled")
        selection_text.bind("<Key>", lambda e: "break")
        selection_text.bind("<Button-1>", lambda e: "break")

    # File processing methods
    def begin_processing(self):
        """Initialize file processing in a separate thread"""
        if not self.selected_paths:
            return

        if not self.provider_var.get():
            self.log_message("Please select an AI provider first", "warning")
            return

        # Reset cancellation flag
        self.processing_cancelled = False

        # Start processing in separate thread
        self.processing_thread = threading.Thread(target=self._process_files)
        self.processing_thread.daemon = True
        self.processing_thread.start()

        # Start progress updates
        self.start_processing()
        self.update_progress()

    def cancel_processing(self):
        """Cancel ongoing processing"""
        self.processing_cancelled = True
        self.log_message(
            "Cancelling... Please wait for current operation to complete.", "warning"
        )
        self.begin_btn["state"] = "disabled"  # Prevent multiple cancel clicks

    def _process_files(self):
        """Background thread for file processing"""
        try:
            # Get provider key from selected name
            provider_name = self.provider_var.get()
            provider_key = self.provider_name_to_key.get(provider_name)
            if not provider_key:
                raise ValueError(f"Provider key not found for '{provider_name}'")

            self.processor.set_provider(provider_key)

            file_count = 0
            file_success_count = 0

            if self.is_directory:
                directory = self.selected_paths[0]

                if self.include_subdirs_var.get():
                    # Process directory and subdirectories
                    print(
                        f"\nProcessing directory: {directory.split(os.sep)[-1]} and all subdirectories",
                        type="info",
                    )
                    for root, _, files in os.walk(directory):
                        for file in files:
                            if self.processing_cancelled:
                                raise InterruptedError("Processing cancelled by user")
                            if file.endswith(".json"):
                                file_count += 1
                                file_success_count += (
                                    1
                                    if self.processor.process_file(
                                        os.path.join(root, file)
                                    )
                                    else 0
                                )
                else:
                    # Process only the selected directory
                    print(
                        f"\nProcessing directory: {directory.split(os.sep)[-1]}",
                        type="info",
                    )
                    for filename in os.listdir(directory):
                        if self.processing_cancelled:
                            raise InterruptedError("Processing cancelled by user")
                        if filename.endswith(".json"):
                            file_count += 1
                            file_success_count += (
                                1
                                if self.processor.process_file(
                                    os.path.join(directory, filename)
                                )
                                else 0
                            )
            else:
                # Process selected files
                for file in self.selected_paths:
                    if self.processing_cancelled:
                        raise InterruptedError("Processing cancelled by user")
                    file_count += 1
                    file_success_count += 1 if self.processor.process_file(file) else 0
            self.processing_queue.put(
                (
                    "success" if file_success_count > 0 else "info",
                    f"\nProcessing complete. {file_success_count} of {file_count} files processed",
                )
            )

        except InterruptedError as e:
            self.processing_queue.put(("warning", f"\n{str(e)}"))
        except Exception as e:
            self.processing_queue.put(("error", f"Error during processing: {e}"))
        finally:
            self.processing_queue.put(("done", None))  # Signal processing is complete

    # Progress tracking methods
    def update_progress(self):
        """Update progress bar and process messages from queue"""
        try:
            while True:
                # Check for messages without blocking
                try:
                    level, message = self.processing_queue.get_nowait()
                    if level == "done":
                        self.stop_processing()
                        return
                    self.log_message(message, level)
                except queue.Empty:
                    break

            # Update progress bar animation
            self.progress_bar.step(5)

            # Schedule next update
            self.after(100, self.update_progress)

        except Exception as e:
            self.log_message(f"Error updating progress: {e}", "error")
            self.stop_processing()

    def start_processing(self):
        """Prepare UI for processing state"""
        self.progress_bar.start()
        self.process_file_btn["state"] = "disabled"
        self.process_dir_btn["state"] = "disabled"
        self.begin_btn["text"] = "Cancel Processing"
        self.begin_btn["command"] = self.cancel_processing

        # Update tooltip and keyboard shortcuts
        self._create_tooltip(self.begin_btn, "Cancel processing (Escape)")
        if self.bindings.get("begin"):
            self.master.unbind("<Control-b>", self.bindings["begin"])
        self.bindings["escape"] = self.master.bind(
            "<Escape>", lambda e: self.cancel_processing()
        )

        # Use configure() on the Frame, not the Button's master
        if isinstance(self.begin_btn.master, tk.Frame):
            self.begin_btn.master.configure(background="#ffe8e8")

        if hasattr(self, "include_subdirs_cb"):
            self.include_subdirs_cb["state"] = "disabled"
        self.progress_var.set("Processing... Please wait")

    def stop_processing(self):
        """Reset UI after processing completes"""
        self.progress_bar.stop()
        self.process_file_btn["state"] = "normal"
        self.process_dir_btn["state"] = "normal"
        self.begin_btn["text"] = "Begin Processing"
        self.begin_btn["command"] = self.begin_processing

        # Restore tooltip and keyboard shortcuts
        self._create_tooltip(self.begin_btn, "Start processing selected files (Ctrl+B)")
        if self.bindings.get("escape"):
            self.master.unbind("<Escape>", self.bindings["escape"])
        self.bindings["begin"] = self.master.bind(
            "<Control-b>", lambda e: self.begin_processing()
        )

        self.begin_btn["state"] = "normal"
        # Use configure() on the Frame, not the Button's master
        if isinstance(self.begin_btn.master, tk.Frame):
            self.begin_btn.master.configure(background="#e8ffe8")

        if hasattr(self, "include_subdirs_cb"):
            self.include_subdirs_cb["state"] = "normal"
        self.progress_var.set("Ready")

    # Utility methods
    def log_message(self, message: str, level: str = "log"):
        """Add a colored message to the log"""
        # Ensure text widget is editable
        self.log_text.configure(state="normal")

        # If message begins with a \n insert a newline first
        if message.startswith("\n"):
            self.log_text.insert(tk.END, "\n", "log")

        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] ", "log")
        self.log_text.insert(tk.END, f"{message.strip("\n ")}\n", level)

        # Make text widget read-only again
        self.log_text.configure(state="disabled")

        # Auto-scroll to the end
        self.log_text.see(tk.END)

        # Force GUI update
        self.update_idletasks()

    def setup_output_redirection(self):
        """Configure output redirection to GUI logging"""

        COLORS = {
            "info": "\033[94m",  # Light blue
            "warning": "\033[93m",  # Yellow
            "error": "\033[91m",  # Light red
            "success": "\033[92m",  # Green
        }
        END_COLOR = "\033[0m"

        def gui_print(*args, **kwargs):
            msg_type = kwargs.pop("type", None)
            text = " ".join(str(arg) for arg in args)

            # Print to terminal with color
            if msg_type in COLORS:
                colored_text = f"{COLORS[msg_type]}{text}{END_COLOR}"
                self.original_print(colored_text, **kwargs)
            else:
                self.original_print(text, **kwargs)

            # Log to GUI
            self.log_message(text, msg_type)

        builtins.print = gui_print

    def on_closing(self):
        """Handle window closing event"""
        try:
            # Cancel any ongoing processing
            if self.processing_thread and self.processing_thread.is_alive():
                self.processing_cancelled = True
                self.processing_thread.join(
                    timeout=1.0
                )  # Wait up to 1 second for thread to finish

            # Restore original print function
            builtins.print = self.original_print

            # Clear the message queue
            while not self.processing_queue.empty():
                try:
                    self.processing_queue.get_nowait()
                except queue.Empty:
                    break

        except Exception as e:
            print(f"Error during cleanup: {e}")
        finally:
            self.master.destroy()


# Application entry point
if __name__ == "__main__":
    root = ThemedTk(theme="arc")
    app = TranscriptProcessorGUI(master=root)
    app.mainloop()