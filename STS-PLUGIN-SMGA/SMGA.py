import os
import json
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from collections import Counter
from mutagen import File
import logging


def load_simplified_genres():
    """Load the simplified genres mapping from a JSON file."""
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    genre_file_path = os.path.join(plugin_dir, "simplified_genre.json")

    if not os.path.exists(genre_file_path):
        raise FileNotFoundError(f"Simplified genre file not found: {genre_file_path}")

    with open(genre_file_path, "r") as file:
        return json.load(file)


def get_audio_files(directory):
    """Recursively find all audio files in a directory."""
    audio_extensions = {'.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg', '.wma'}
    audio_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if os.path.splitext(file)[1].lower() in audio_extensions:
                audio_files.append(os.path.join(root, file))
    return audio_files


def get_genre(file_path):
    """Extract the genre metadata from an audio file."""
    try:
        audio = File(file_path)
        if audio:
            for tag in ['genre', 'GENRE', 'TCON']:  # Common tags for genre
                if tag in audio.tags:
                    genre = audio.tags[tag]
                    if isinstance(genre, list):
                        genre = genre[0]
                    return [g.strip().lower() for g in str(genre).split(';')]
    except Exception:
        pass
    return []


def map_to_simplified_genres(complex_genres, simplified_keywords):
    """Map complex genres to simplified categories."""
    simplified_genres = []
    unmapped_count = 0  # Track the number of unmapped genres

    for genre in complex_genres:
        genre_lower = genre.lower().strip()  # Normalize case
        matched = None
        for simplified_genre, keywords in simplified_keywords.items():
            if any(keyword in genre_lower for keyword in keywords):  # Check for substring matches
                matched = simplified_genre
                break
        if matched:
            simplified_genres.append(matched)
        else:
            simplified_genres.append(genre.title())  # Default to title-cased genre
            unmapped_count += 1  # Increment the unmapped count

    return simplified_genres, unmapped_count



def calculate_genre_distribution(audio_files, use_simple_genres, simplified_keywords):
    """Calculate the percentage distribution of genres."""
    genres = []
    for file in audio_files:
        genre_list = get_genre(file)
        if use_simple_genres:
            genre_list = map_to_simplified_genres(genre_list, simplified_keywords)
        genres.extend(genre_list)

    genre_count = Counter(genres)
    total_tracks = len(genres)

    if total_tracks == 0:
        return genre_count, {}, 0

    genre_percentage = {genre: (count / total_tracks) * 100 for genre, count in genre_count.items()}
    return genre_count, genre_percentage


def calculate_overlap(audio_files):
    """Find the number of songs that belong to multiple genres."""
    overlap_count = 0
    for file in audio_files:
        genres = get_genre(file)
        if len(genres) > 1:
            overlap_count += 1
    return overlap_count


def smga_main_logic(parent_widget, simplified_keywords, logger):
    """Core logic for the SMGA plugin."""
    logger.info("Initializing SMGA UI...")

    # Locate the UI file
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    ui_file_path = os.path.join(plugin_dir, "SMGA.ui")

    if not os.path.exists(ui_file_path):
        logger.error(f"UI file not found at: {ui_file_path}")
        QtWidgets.QMessageBox.critical(None, "Error", f"UI file not found at: {ui_file_path}")
        return

    plugin_widget = uic.loadUi(ui_file_path)

    # Check if the parent_widget already has a layout
    if parent_widget.layout():
        logger.warning("Parent widget already has a layout. Adding the plugin widget to the existing layout.")
        parent_widget.layout().addWidget(plugin_widget)
    else:
        logger.info("Setting a new layout for the parent widget.")
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(plugin_widget)
        parent_widget.setLayout(layout)

    # UI elements
    select_directory_button = plugin_widget.findChild(QtWidgets.QPushButton, "pushButton_select")
    directory_input = plugin_widget.findChild(QtWidgets.QLineEdit, "lineEdit_directory")
    analyze_button = plugin_widget.findChild(QtWidgets.QPushButton, "pushButton_analyze")
    results_table = plugin_widget.findChild(QtWidgets.QTableView, "tableView_results")
    overlap_label = plugin_widget.findChild(QtWidgets.QLabel, "genre_overlap_value")
    simple_radio = plugin_widget.findChild(QtWidgets.QRadioButton, "radioButton")
    complex_radio = plugin_widget.findChild(QtWidgets.QRadioButton, "radioButton_complex")

    # Set defaults
    complex_radio.setChecked(True)

    def select_directory():
        """Open a dialog to select a directory and update the input field."""
        directory = QtWidgets.QFileDialog.getExistingDirectory(plugin_widget, "Select Music Directory")
        if directory:
            directory_input.setText(directory)
            logger.info(f"Directory selected: {directory}")
        else:
            logger.warning("No directory selected.")

    def analyze():
        """Analyze the audio files in the selected directory."""
        analyze_button.setText("Analyzing...")
        analyze_button.setEnabled(False)

        # Determine which analysis type is selected
        if simple_radio.isChecked():
            logger.info("Simple Analysis Started.")
        else:
            logger.info("Complex Analysis Started.")

        QtCore.QTimer.singleShot(100, perform_analysis)

    def perform_analysis():
        """Perform the actual analysis logic."""
        try:
            selected_directory = directory_input.text().strip()
            if not selected_directory:
                logger.warning("No directory selected for analysis.")
                QtWidgets.QMessageBox.warning(plugin_widget, "Error", "Please select a directory first.")
                return

            use_simple_genres = simple_radio.isChecked()
            audio_files = get_audio_files(selected_directory)

            if not audio_files:
                logger.info("No audio files found in the selected directory.")
                QtWidgets.QMessageBox.information(plugin_widget, "Analysis", "No audio files found in the selected directory.")
                return

            genres = [genre for file in audio_files for genre in get_genre(file)]
            unmapped_count = 0

            if use_simple_genres:
                genres, unmapped_count = map_to_simplified_genres(genres, simplified_keywords)

            genre_count = Counter(genres)
            total_tracks = len(genres)

            overlap_count = calculate_overlap(audio_files)
            overlap_label.setText(str(overlap_count))
            display_results(genre_count, {genre: (count / total_tracks) * 100 for genre, count in genre_count.items()})

            if use_simple_genres:
                logger.info(f"Simple Analysis Complete: {len(audio_files)} audio files processed. {len(genre_count)} genres found.")
                if unmapped_count > 0:
                    logger.warning(f"{unmapped_count} songs could not be simplified into a genre.")
            else:
                logger.info(f"Complex Analysis Complete: {len(audio_files)} audio files processed. {len(genre_count)} genres found.")
        except Exception as e:
            logger.error(f"An error occurred during analysis: {e}")
            QtWidgets.QMessageBox.critical(plugin_widget, "Error", f"An error occurred: {e}")
        finally:
            analyze_button.setText("Analyze")
            analyze_button.setEnabled(True)



    def display_results(genre_count, genre_percentage):
        """Populate the table with genre distribution data."""
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Genre", "Count", "Percentage (%)"])

        for genre, count in sorted(genre_count.items(), key=lambda item: genre_percentage.get(item[0], 0), reverse=True):
            percentage = genre_percentage.get(genre, 0)
            model.appendRow([
                QStandardItem(genre.title()),
                QStandardItem(str(count)),
                QStandardItem(f"{percentage:.2f}")
            ])

        results_table.setModel(model)
        results_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

    select_directory_button.clicked.connect(select_directory)
    analyze_button.clicked.connect(analyze)

    return plugin_widget


def main(parent_widget=None, parent_logger=None):
    """Main entry point for the SMGA plugin."""
    logger = parent_logger.getChild("SMGA") if parent_logger else logging.getLogger("SMGA_Fallback")

    logger.info("SMGA Plugin initialized.")

    try:
        simplified_keywords = load_simplified_genres()
    except FileNotFoundError as e:
        logger.error(str(e))
        QtWidgets.QMessageBox.critical(None, "Error", str(e))
        return None

    return smga_main_logic(parent_widget, simplified_keywords, logger)
