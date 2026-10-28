# extract_corpus.py - run once. Pulls the embedded corpus.jsonl out of the assignment PDF.
import os
from pypdf import PdfReader

reader = PdfReader('source/Batch5_Candidate_Assignment_Complete.pdf')
os.makedirs('data', exist_ok=True)

# reader.attachments is a dictionary: file name -> list of file contents (bytes)
for name, contents in reader.attachments.items():
    print('Found attachment:', name)
    if name.endswith('corpus.jsonl'):
        # 'wb' means write raw bytes, so the file is saved exactly as it was (unchanged)
        with open('data/corpus.jsonl', 'wb') as f:
            f.write(contents[0])
        print('Saved data/corpus.jsonl')