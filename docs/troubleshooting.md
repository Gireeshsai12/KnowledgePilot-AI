# Troubleshooting

- If the port is occupied, copy .env.example to .env and change KP_PORT for Compose. Use a different --port for a native launch.
- If a PDF yields no text, check that you can select and copy text in a PDF viewer. Convert scanned pages using a trusted OCR tool before uploading.
- If search is empty, shorten the query and use words that appear in the source or select All documents.
- If account access has expired, sign in again. If sharing fails, check that the target email already has a local account.
- If Docker is unavailable, use the Python 3.12 commands in the README. The first install needs access to an index with the pinned wheels for your platform.
