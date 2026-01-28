#!/usr/bin/env python3
"""
AnthoLume to BookLore Sync Bridge

Syncs reading activity from AnthoLume (SQLite) to BookLore (MariaDB).
Matches books by title/author/filename and syncs reading sessions.
"""

import os
import re
import time
import sqlite3
import pymysql
from datetime import datetime, timedelta
from difflib import SequenceMatcher

# Configuration
ANTHOLUME_DB = os.getenv('ANTHOLUME_DB', '/antholume/antholume.db')
BOOKLORE_HOST = os.getenv('BOOKLORE_DB_HOST', 'mariadb')
BOOKLORE_PORT = int(os.getenv('BOOKLORE_DB_PORT', 3306))
BOOKLORE_DB = os.getenv('BOOKLORE_DB_NAME', 'booklore')
BOOKLORE_USER = os.getenv('BOOKLORE_DB_USER', 'booklore')
BOOKLORE_PASSWORD = os.getenv('BOOKLORE_DB_PASSWORD', '')
SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL', 300))  # 5 minutes default
BOOKLORE_USER_ID = int(os.getenv('BOOKLORE_USER_ID', 1))  # BookLore user ID

# Track synced activities to avoid duplicates
SYNC_STATE_FILE = '/config/sync_state.txt'

# Cache for book matching
book_cache = {}


def get_antholume_connection():
    return sqlite3.connect(ANTHOLUME_DB)


def get_booklore_connection():
    return pymysql.connect(
        host=BOOKLORE_HOST,
        port=BOOKLORE_PORT,
        user=BOOKLORE_USER,
        password=BOOKLORE_PASSWORD,
        database=BOOKLORE_DB,
        cursorclass=pymysql.cursors.DictCursor
    )


def get_last_sync_id():
    """Get the last synced activity ID"""
    try:
        if os.path.exists(SYNC_STATE_FILE):
            with open(SYNC_STATE_FILE, 'r') as f:
                return int(f.read().strip())
    except:
        pass
    return 0


def save_last_sync_id(activity_id):
    """Save the last synced activity ID"""
    os.makedirs(os.path.dirname(SYNC_STATE_FILE), exist_ok=True)
    with open(SYNC_STATE_FILE, 'w') as f:
        f.write(str(activity_id))


def normalize_text(text):
    """Normalize text for matching"""
    if not text:
        return ''
    # Lowercase, remove accents approximation, remove special chars
    text = text.lower().strip()
    # Remove file extensions
    for ext in ['.epub', '.pdf', '.mobi', '.azw3', '.cbz', '.cbr', '.azw']:
        if text.endswith(ext):
            text = text[:-len(ext)]
    # Remove common patterns like "[hash]" at the end
    text = re.sub(r'\s*\[[a-f0-9]+\]\s*$', '', text)
    # Remove special characters but keep spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def similarity(a, b):
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def load_booklore_books(cursor):
    """Load all BookLore books into cache"""
    global book_cache
    cursor.execute("""
        SELECT b.id, bm.title, GROUP_CONCAT(DISTINCT a.name SEPARATOR ', ') as authors,
               GROUP_CONCAT(DISTINCT bf.file_name SEPARATOR '|') as filenames,
               GROUP_CONCAT(DISTINCT COALESCE(bf.initial_hash, bf.current_hash) SEPARATOR '|') as hashes
        FROM book b
        JOIN book_metadata bm ON b.id = bm.book_id
        LEFT JOIN book_metadata_author_mapping bam ON bm.book_id = bam.book_id
        LEFT JOIN author a ON bam.author_id = a.id
        LEFT JOIN book_file bf ON b.id = bf.book_id
        WHERE b.deleted = 0
        GROUP BY b.id, bm.title
    """)

    book_cache = {}
    for row in cursor.fetchall():
        book_cache[row['id']] = {
            'title': row['title'] or '',
            'authors': row['authors'] or '',
            'filenames': (row['filenames'] or '').split('|'),
            'hashes': [h for h in (row['hashes'] or '').split('|') if h]
        }
    print(f"[{datetime.now()}] Loaded {len(book_cache)} books from BookLore")


def find_booklore_book(antholume_doc):
    """Find matching BookLore book for an AnthoLume document"""
    title = antholume_doc.get('title', '') or ''
    author = antholume_doc.get('author', '') or ''
    filepath = antholume_doc.get('filepath', '') or ''
    doc_id = antholume_doc.get('id', '') or ''
    md5 = antholume_doc.get('md5', '') or ''

    # Extract filename from filepath
    filename = os.path.basename(filepath) if filepath else ''

    # First try: exact MD5 match (highest priority)
    if md5:
        for book_id, book in book_cache.items():
            if md5 in book.get('hashes', []):
                print(f"[{datetime.now()}] MD5 match: '{title or doc_id}' -> '{book.get('title', 'Unknown')}' (hash: {md5[:8]}...)")
                return book_id

    # Second try: hash prefix match (KOReader partial MD5 vs BookLore full hash)
    # doc_id in AnthoLume is the partial MD5 from KOReader
    if doc_id:
        doc_id_lower = doc_id.lower()
        for book_id, book in book_cache.items():
            for h in book.get('hashes', []):
                if h:
                    h_lower = h.lower()
                    # Check if one is prefix of the other (at least 16 chars match)
                    if len(doc_id_lower) >= 16 and len(h_lower) >= 16:
                        if doc_id_lower.startswith(h_lower[:16]) or h_lower.startswith(doc_id_lower[:16]):
                            print(f"[{datetime.now()}] Hash prefix match: '{title or doc_id[:16]}...' -> '{book.get('title', 'Unknown')}'")
                            return book_id

    best_match = None
    best_score = 0

    for book_id, book in book_cache.items():
        score = 0

        # Try exact title match (normalized)
        if title and book['title']:
            title_sim = similarity(title, book['title'])
            if title_sim > 0.8:
                score += title_sim * 50

        # Try author match
        if author and book['authors']:
            author_sim = similarity(author, book['authors'])
            if author_sim > 0.5:
                score += author_sim * 30

        # Try filename match
        if filename:
            for bf in book['filenames']:
                if bf:
                    fn_sim = similarity(filename, bf)
                    if fn_sim > 0.6:
                        score += fn_sim * 40
                        break

        # If document ID contains part of filename or hash
        if doc_id:
            for bf in book['filenames']:
                if bf and doc_id[:8].lower() in normalize_text(bf):
                    score += 20
                    break
            # Also check if doc_id matches any hash prefix
            for h in book.get('hashes', []):
                if h and (doc_id.lower().startswith(h[:8].lower()) or h.lower().startswith(doc_id[:8].lower())):
                    score += 30
                    break

        if score > best_score:
            best_score = score
            best_match = book_id

    # Only return if we have a decent match
    if best_score >= 40:
        matched_book = book_cache.get(best_match, {})
        print(f"[{datetime.now()}] Matched '{title or doc_id}' -> '{matched_book.get('title', 'Unknown')}' (score: {best_score:.1f})")
        return best_match

    return None


def get_book_type(title, filepath):
    """Determine book type from title/filepath"""
    check = (title or '') + (filepath or '')
    check = check.lower()
    if '.pdf' in check:
        return 'PDF'
    if '.cbz' in check or '.cbr' in check or '.cb7' in check:
        return 'CBX'
    return 'EPUB'


def sync_activities():
    """Sync reading activities from AnthoLume to BookLore"""
    last_sync_id = get_last_sync_id()
    print(f"[{datetime.now()}] Starting activity sync from ID {last_sync_id}")

    try:
        antholume_conn = get_antholume_connection()
        antholume_cursor = antholume_conn.cursor()

        booklore_conn = get_booklore_connection()
        booklore_cursor = booklore_conn.cursor()

        # Load BookLore books cache
        load_booklore_books(booklore_cursor)

        # Get new activities with document info
        antholume_cursor.execute("""
            SELECT a.id, a.document_id, a.start_time, a.duration,
                   a.start_percentage, a.end_percentage,
                   d.title, d.author, d.md5, d.filepath, d.id as doc_id
            FROM activity a
            JOIN documents d ON a.document_id = d.id
            WHERE a.id > ?
            ORDER BY a.id ASC
        """, (last_sync_id,))

        activities = antholume_cursor.fetchall()
        print(f"[{datetime.now()}] Found {len(activities)} new activities")

        synced_count = 0
        max_id = last_sync_id

        for activity in activities:
            (activity_id, document_id, start_time, duration,
             start_percentage, end_percentage, title, author, md5, filepath, doc_id) = activity

            max_id = max(max_id, activity_id)

            antholume_doc = {
                'id': doc_id,
                'title': title,
                'author': author,
                'md5': md5,
                'filepath': filepath
            }

            book_id = find_booklore_book(antholume_doc)

            if not book_id:
                print(f"[{datetime.now()}] No match for: '{title or doc_id}' by '{author or 'Unknown'}'")
                continue

            # Parse start_time
            try:
                if isinstance(start_time, str):
                    if 'T' in start_time:
                        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    else:
                        start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                else:
                    start_dt = datetime.fromtimestamp(start_time)
            except:
                start_dt = datetime.now()

            # Calculate end time
            duration_secs = int(duration or 0)
            end_dt = start_dt + timedelta(seconds=duration_secs)

            # Calculate progress
            start_pct = float(start_percentage or 0) * 100
            end_pct = float(end_percentage or 0) * 100
            progress_delta = end_pct - start_pct

            book_type = get_book_type(title, filepath)

            # Check for duplicate
            booklore_cursor.execute("""
                SELECT id FROM reading_sessions
                WHERE user_id = %s AND book_id = %s
                  AND ABS(TIMESTAMPDIFF(SECOND, start_time, %s)) < 60
                LIMIT 1
            """, (BOOKLORE_USER_ID, book_id, start_dt))

            if booklore_cursor.fetchone():
                continue

            # Insert reading session
            booklore_cursor.execute("""
                INSERT INTO reading_sessions
                (user_id, book_id, book_type, start_time, end_time, duration_seconds,
                 start_progress, end_progress, progress_delta, start_location, end_location, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                BOOKLORE_USER_ID, book_id, book_type, start_dt, end_dt, duration_secs,
                start_pct, end_pct, progress_delta,
                f'antholume:{document_id}', f'antholume:{document_id}'
            ))

            synced_count += 1
            book_title = book_cache.get(book_id, {}).get('title', 'Unknown')
            print(f"[{datetime.now()}] Synced: '{book_title}' - {duration_secs}s, {progress_delta:.1f}% progress")

        booklore_conn.commit()

        if max_id > last_sync_id:
            save_last_sync_id(max_id)

        print(f"[{datetime.now()}] Activity sync complete: {synced_count} sessions synced")

        antholume_conn.close()
        booklore_conn.close()

    except Exception as e:
        print(f"[{datetime.now()}] Activity sync error: {e}")
        import traceback
        traceback.print_exc()


def sync_progress():
    """Sync current reading progress from AnthoLume to BookLore"""
    print(f"[{datetime.now()}] Starting progress sync...")

    try:
        antholume_conn = get_antholume_connection()
        antholume_cursor = antholume_conn.cursor()

        booklore_conn = get_booklore_connection()
        booklore_cursor = booklore_conn.cursor()

        # Ensure cache is loaded
        if not book_cache:
            load_booklore_books(booklore_cursor)

        # Get document progress with full document info
        antholume_cursor.execute("""
            SELECT dp.document_id, dp.percentage, dp.progress, dp.device_id,
                   d.title, d.author, d.md5, d.filepath, d.id as doc_id
            FROM document_progress dp
            JOIN documents d ON dp.document_id = d.id
        """)

        progress_records = antholume_cursor.fetchall()
        updated_count = 0

        for record in progress_records:
            (document_id, percentage, progress_str, device_id,
             title, author, md5, filepath, doc_id) = record

            antholume_doc = {
                'id': doc_id,
                'title': title,
                'author': author,
                'md5': md5,
                'filepath': filepath
            }

            book_id = find_booklore_book(antholume_doc)

            if not book_id:
                continue

            # BookLore expects decimal (0.0-1.0), not percentage (0-100)
            progress_percent = float(percentage or 0)

            # Check if progress exists
            booklore_cursor.execute("""
                SELECT id, koreader_progress_percent FROM user_book_progress
                WHERE user_id = %s AND book_id = %s
            """, (BOOKLORE_USER_ID, book_id))

            existing = booklore_cursor.fetchone()

            if existing:
                # Only update if progress is higher or significantly different
                current_pct = float(existing.get('koreader_progress_percent') or 0)
                if progress_percent > current_pct or abs(progress_percent - current_pct) > 1:
                    booklore_cursor.execute("""
                        UPDATE user_book_progress
                        SET koreader_progress = %s,
                            koreader_progress_percent = %s,
                            koreader_device = %s,
                            koreader_device_id = %s,
                            koreader_last_sync_time = NOW(),
                            last_read_time = NOW(),
                            read_status = CASE WHEN %s >= 0.95 THEN 'READ'
                                              WHEN %s > 0 THEN 'READING'
                                              ELSE read_status END
                        WHERE user_id = %s AND book_id = %s
                    """, (progress_str, progress_percent, 'AnthoLume', device_id,
                          progress_percent, progress_percent, BOOKLORE_USER_ID, book_id))
                    updated_count += 1
            else:
                # Insert new progress
                read_status = 'READ' if progress_percent >= 0.95 else 'READING' if progress_percent > 0 else 'UNREAD'
                booklore_cursor.execute("""
                    INSERT INTO user_book_progress
                    (user_id, book_id, koreader_progress, koreader_progress_percent,
                     koreader_device, koreader_device_id, koreader_last_sync_time,
                     last_read_time, read_status)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW(), %s)
                """, (BOOKLORE_USER_ID, book_id, progress_str, progress_percent,
                      'AnthoLume', device_id, read_status))
                updated_count += 1

        booklore_conn.commit()
        print(f"[{datetime.now()}] Progress sync complete: {updated_count} books updated")

        antholume_conn.close()
        booklore_conn.close()

    except Exception as e:
        print(f"[{datetime.now()}] Progress sync error: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("=" * 60)
    print("AnthoLume to BookLore Sync Bridge")
    print("=" * 60)
    print(f"AnthoLume DB: {ANTHOLUME_DB}")
    print(f"BookLore DB: {BOOKLORE_HOST}:{BOOKLORE_PORT}/{BOOKLORE_DB}")
    print(f"Sync interval: {SYNC_INTERVAL} seconds")
    print(f"BookLore User ID: {BOOKLORE_USER_ID}")
    print("=" * 60)

    while True:
        sync_activities()
        sync_progress()
        print(f"[{datetime.now()}] Sleeping for {SYNC_INTERVAL} seconds...")
        time.sleep(SYNC_INTERVAL)


if __name__ == '__main__':
    main()
