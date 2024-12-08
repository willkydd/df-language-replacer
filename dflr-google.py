import argparse
import re
import os
from deep_translator import GoogleTranslator
from unidecode import unidecode
from tqdm import tqdm
import sys

# Define valid language files
LANG_FILES = [
    "language_DWARF.txt",
    "language_ELF.txt",
    "language_GOBLIN.txt",
    "language_HUMAN.txt"
]
PER_LINE_TRANS_DELAY = 0.21  # Delay per line if needed for rate-limiting
BATCH_SIZE = 10  # Number of lines to process in one batch

# Function to convert text to CP437-compatible form
def to_cp437_compatible(text):
    ascii_text = unidecode(text)
    # Encode to CP437, replacing unsupported characters with '?'
    cp437_text = ascii_text.encode('cp437', errors='replace').decode('cp437')    
    return cp437_text

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('lang_file', help='File containing language data')
parser.add_argument('lang_code', type=str, help='Language code to translate to')
args = parser.parse_args()

# Read and validate input file
input_lang_fname = os.path.basename(args.lang_file)  # Extract file name from the path
if input_lang_fname not in LANG_FILES:
    print(f"Error: {input_lang_fname} is not a valid language file. Exiting.")
    exit(1)
else:
    input_lang_fullpath = args.lang_file
    # Determine output file path
    output_lang_fname = f"{os.path.splitext(input_lang_fname)[0]}-{args.lang_code}.txt"
    output_lang_fullpath = os.path.join(os.path.dirname(input_lang_fullpath), output_lang_fname)

# Translator initialization
translator = GoogleTranslator(source='en', target=args.lang_code)
supported_languages = translator.get_supported_languages(as_dict=True)
if args.lang_code not in supported_languages.values():
    print(f"Language {args.lang_code} not recognised.")
    print(f"Valid languages: {supported_languages}")
    exit(1)

# Read the total number of lines for progress tracking
total_lines = sum(1 for _ in open(input_lang_fullpath, 'r', encoding='cp437'))

# Batch translation logic
def translate_lines(lines, translator):
    to_translate = []
    pre_strings = []
    for line in lines:
        match = re.search(r'([\t ]*)\[T_WORD:([^\:]+):([^\]]+)\]', line)
        if match:
            pre_string, en_word, fo_word = match.group(1), match.group(2), match.group(3)
            base_word = re.match(r'^[^ _]+', en_word).group(0)  # Extract the base word
            to_translate.append(base_word)
            pre_strings.append((pre_string, en_word))
        else:
            pre_strings.append(line)

    # Perform batch translation
    translated_words = []
    if to_translate:
        try:
            translated_words = translator.translate_batch(to_translate)
        except Exception as e:
            print(f"Error during batch translation: {e}")
            sys.exit(1)

    # Map translations back to the lines
    translated_lines = []
    trans_idx = 0
    for entry in pre_strings:
        if isinstance(entry, tuple):
            pre_string, en_word = entry
            trans_word = translated_words[trans_idx] if trans_idx < len(translated_words) else "?"
            trans_word = re.sub(r'\s+', '-', trans_word)  # Ensure single word
            trans_word = to_cp437_compatible(trans_word)  # Convert to CP437-compatible encoding
            trans_word = trans_word.replace('`', '')  # Removes all backticks
            trans_word=trans_word.lower()
            translated_lines.append(f"{pre_string}[T_WORD:{en_word}:{trans_word}]\n")
            trans_idx += 1
        else:
            translated_lines.append(entry)
    return translated_lines

# Open the files for input and output
with open(input_lang_fullpath, 'r', encoding='cp437') as fin, open(output_lang_fullpath, 'w', encoding='cp437') as fout:
    buffer = []
    for line in tqdm(fin, total=total_lines, desc=f"Translating {output_lang_fname}"):
        buffer.append(line)
        if len(buffer) >= BATCH_SIZE:
            translated = translate_lines(buffer, translator)
            fout.writelines(translated)
            fout.flush()
            buffer = []

    # Process any remaining lines
    if buffer:
        translated = translate_lines(buffer, translator)
        fout.writelines(translated)
        fout.flush()
