#!/usr/bin/env python3
import os
import time
from datetime import datetime, timedelta
import pymysql
from prometheus_client import start_http_server, Gauge, Counter, Info

# Database configuration from environment
DB_HOST = os.getenv('DB_HOST', 'mariadb')
DB_PORT = int(os.getenv('DB_PORT', 3306))
DB_NAME = os.getenv('DB_NAME', 'booklore')
DB_USER = os.getenv('DB_USER', 'booklore')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
EXPORTER_PORT = int(os.getenv('EXPORTER_PORT', 9090))
SCRAPE_INTERVAL = int(os.getenv('SCRAPE_INTERVAL', 60))

# =============================================================================
# LIBRARY METRICS
# =============================================================================
booklore_books_total = Gauge('booklore_books_total', 'Total number of books', ['library', 'read_status'])
booklore_users_total = Gauge('booklore_users_total', 'Total number of users')
booklore_libraries_total = Gauge('booklore_libraries_total', 'Total number of libraries')
booklore_authors_total = Gauge('booklore_authors_total', 'Total number of authors')
booklore_shelves_total = Gauge('booklore_shelves_total', 'Total number of shelves')
booklore_categories_total = Gauge('booklore_categories_total', 'Total number of categories')
booklore_books_by_type = Gauge('booklore_books_by_type', 'Number of books by file type', ['file_type'])
booklore_books_by_category = Gauge('booklore_books_by_category', 'Number of books by category', ['category'])
booklore_books_by_author = Gauge('booklore_books_by_author', 'Number of books by author', ['author'])
booklore_books_with_series = Gauge('booklore_books_with_series', 'Number of books that are part of a series')
booklore_series_total = Gauge('booklore_series_total', 'Total number of unique series')

# =============================================================================
# USER READING STATUS METRICS
# =============================================================================
booklore_user_books_by_status = Gauge('booklore_user_books_by_status', 'Books by read status per user', ['user', 'status'])
booklore_user_books_with_progress = Gauge('booklore_user_books_with_progress', 'Books with reading progress', ['user'])
booklore_user_books_finished = Gauge('booklore_user_books_finished', 'Number of finished books', ['user'])
booklore_user_average_progress = Gauge('booklore_user_average_progress_percent', 'Average reading progress percentage', ['user'])
booklore_user_books_rated = Gauge('booklore_user_books_rated', 'Number of books rated by user', ['user'])
booklore_user_average_rating = Gauge('booklore_user_average_rating', 'Average book rating by user', ['user'])
booklore_user_books_by_progress_range = Gauge('booklore_user_books_by_progress_range', 'Books by reading progress range', ['user', 'progress_range'])
booklore_user_books_by_rating = Gauge('booklore_user_books_by_rating', 'Books by personal rating', ['user', 'rating'])
booklore_reading_time_by_category = Gauge('booklore_reading_time_by_category_seconds', 'Reading time by category/genre in seconds', ['user', 'category'])

# =============================================================================
# READING SESSION METRICS
# =============================================================================
booklore_reading_sessions_total = Gauge('booklore_reading_sessions_total', 'Total number of reading sessions')
booklore_reading_time_total_seconds = Gauge('booklore_reading_time_total_seconds', 'Total reading time in seconds', ['user'])
booklore_reading_sessions_by_date = Gauge('booklore_reading_sessions_by_date', 'Reading sessions by date', ['user', 'date'])
booklore_reading_time_by_date = Gauge('booklore_reading_time_by_date_seconds', 'Reading time by date in seconds', ['user', 'date'])
booklore_reading_progress_by_date = Gauge('booklore_reading_progress_by_date', 'Reading progress delta by date', ['user', 'date'])
booklore_reading_sessions_by_book_type = Gauge('booklore_reading_sessions_by_book_type', 'Reading sessions by book type', ['user', 'book_type'])
booklore_reading_time_by_book_type = Gauge('booklore_reading_time_by_book_type_seconds', 'Reading time by book type', ['user', 'book_type'])

# =============================================================================
# READING STREAKS AND HABITS
# =============================================================================
booklore_current_reading_streak_days = Gauge('booklore_current_reading_streak_days', 'Current consecutive days reading streak', ['user'])
booklore_longest_reading_streak_days = Gauge('booklore_longest_reading_streak_days', 'Longest reading streak in days', ['user'])
booklore_days_read_this_month = Gauge('booklore_days_read_this_month', 'Number of days read this month', ['user'])
booklore_days_read_this_year = Gauge('booklore_days_read_this_year', 'Number of days read this year', ['user'])
booklore_average_session_duration_seconds = Gauge('booklore_average_session_duration_seconds', 'Average reading session duration', ['user'])
booklore_reading_sessions_by_hour = Gauge('booklore_reading_sessions_by_hour', 'Reading sessions by hour of day', ['user', 'hour'])
booklore_reading_sessions_by_weekday = Gauge('booklore_reading_sessions_by_weekday', 'Reading sessions by day of week', ['user', 'weekday'])

# =============================================================================
# BOOKS FINISHED OVER TIME
# =============================================================================
booklore_books_finished_by_month = Gauge('booklore_books_finished_by_month', 'Books finished by month', ['user', 'ym'])
booklore_books_finished_this_year = Gauge('booklore_books_finished_this_year', 'Books finished this year', ['user'])
booklore_books_finished_this_month = Gauge('booklore_books_finished_this_month', 'Books finished this month', ['user'])

# =============================================================================
# RECENT ACTIVITY
# =============================================================================
booklore_last_read_timestamp = Gauge('booklore_last_read_timestamp', 'Timestamp of last reading activity', ['user'])
booklore_books_read_last_7_days = Gauge('booklore_books_read_last_7_days', 'Unique books read in last 7 days', ['user'])
booklore_reading_time_last_7_days_seconds = Gauge('booklore_reading_time_last_7_days_seconds', 'Reading time in last 7 days', ['user'])
booklore_reading_time_last_30_days_seconds = Gauge('booklore_reading_time_last_30_days_seconds', 'Reading time in last 30 days', ['user'])

# =============================================================================
# KOREADER SYNC METRICS
# =============================================================================
booklore_koreader_synced_books = Gauge('booklore_koreader_synced_books', 'Books synced with KOReader', ['user', 'device'])
booklore_koreader_last_sync_timestamp = Gauge('booklore_koreader_last_sync_timestamp', 'Last KOReader sync timestamp', ['user'])

# =============================================================================
# SCRAPE METRICS
# =============================================================================
booklore_last_scrape = Gauge('booklore_last_scrape_timestamp', 'Timestamp of last successful scrape')
booklore_scrape_errors = Counter('booklore_scrape_errors_total', 'Total number of scrape errors')
booklore_scrape_duration = Gauge('booklore_scrape_duration_seconds', 'Duration of last scrape')


def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )


def clear_gauge_metrics(gauge):
    """Clear all label combinations for a gauge"""
    gauge._metrics.clear()


def collect_metrics():
    start_time = time.time()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # =====================================================================
        # LIBRARY METRICS
        # =====================================================================

        # Books by library and read status
        cursor.execute("""
            SELECT l.name as library, COALESCE(b.read_status, 'UNREAD') as read_status, COUNT(*) as count
            FROM book b
            JOIN library l ON b.library_id = l.id
            WHERE b.deleted = 0
            GROUP BY l.name, b.read_status
        """)
        clear_gauge_metrics(booklore_books_total)
        for row in cursor.fetchall():
            booklore_books_total.labels(library=row['library'], read_status=row['read_status']).set(row['count'])

        # Total users
        cursor.execute("SELECT COUNT(*) as count FROM users")
        booklore_users_total.set(cursor.fetchone()['count'])

        # Total libraries
        cursor.execute("SELECT COUNT(*) as count FROM library")
        booklore_libraries_total.set(cursor.fetchone()['count'])

        # Total authors
        cursor.execute("SELECT COUNT(*) as count FROM author")
        booklore_authors_total.set(cursor.fetchone()['count'])

        # Total shelves
        cursor.execute("SELECT COUNT(*) as count FROM shelf")
        booklore_shelves_total.set(cursor.fetchone()['count'])

        # Total categories
        cursor.execute("SELECT COUNT(*) as count FROM category")
        booklore_categories_total.set(cursor.fetchone()['count'])

        # Books by file type
        cursor.execute("""
            SELECT UPPER(SUBSTRING_INDEX(file_name, '.', -1)) as file_type, COUNT(DISTINCT book_id) as count
            FROM book_file
            GROUP BY file_type
        """)
        clear_gauge_metrics(booklore_books_by_type)
        for row in cursor.fetchall():
            booklore_books_by_type.labels(file_type=row['file_type']).set(row['count'])

        # Books by category (top 20)
        cursor.execute("""
            SELECT c.name, COUNT(DISTINCT bcm.book_id) as book_count
            FROM category c
            JOIN book_metadata_category_mapping bcm ON c.id = bcm.category_id
            GROUP BY c.id, c.name
            ORDER BY book_count DESC
            LIMIT 20
        """)
        clear_gauge_metrics(booklore_books_by_category)
        for row in cursor.fetchall():
            booklore_books_by_category.labels(category=row['name']).set(row['book_count'])

        # Books by author (top 20)
        cursor.execute("""
            SELECT a.name, COUNT(DISTINCT bam.book_id) as book_count
            FROM author a
            JOIN book_metadata_author_mapping bam ON a.id = bam.author_id
            GROUP BY a.id, a.name
            ORDER BY book_count DESC
            LIMIT 20
        """)
        clear_gauge_metrics(booklore_books_by_author)
        for row in cursor.fetchall():
            booklore_books_by_author.labels(author=row['name']).set(row['book_count'])

        # Series metrics
        cursor.execute("""
            SELECT COUNT(*) as count FROM book_metadata WHERE series_name IS NOT NULL AND series_name != ''
        """)
        booklore_books_with_series.set(cursor.fetchone()['count'])

        cursor.execute("""
            SELECT COUNT(DISTINCT series_name) as count FROM book_metadata WHERE series_name IS NOT NULL AND series_name != ''
        """)
        booklore_series_total.set(cursor.fetchone()['count'])

        # =====================================================================
        # USER READING STATUS METRICS
        # =====================================================================

        # Books by read status per user
        cursor.execute("""
            SELECT u.username, COALESCE(ubp.read_status, 'NONE') as status, COUNT(*) as count
            FROM users u
            LEFT JOIN user_book_progress ubp ON u.id = ubp.user_id
            GROUP BY u.id, u.username, ubp.read_status
        """)
        clear_gauge_metrics(booklore_user_books_by_status)
        for row in cursor.fetchall():
            if row['status']:
                booklore_user_books_by_status.labels(user=row['username'], status=row['status']).set(row['count'])

        # Books with progress
        cursor.execute("""
            SELECT u.username, COUNT(*) as count
            FROM users u
            JOIN user_book_progress ubp ON u.id = ubp.user_id
            WHERE COALESCE(ubp.pdf_progress_percent, ubp.epub_progress_percent, ubp.cbx_progress_percent, ubp.koreader_progress_percent, 0) > 0
            GROUP BY u.id, u.username
        """)
        clear_gauge_metrics(booklore_user_books_with_progress)
        for row in cursor.fetchall():
            booklore_user_books_with_progress.labels(user=row['username']).set(row['count'])

        # Books finished per user
        cursor.execute("""
            SELECT u.username, COUNT(*) as count
            FROM users u
            JOIN user_book_progress ubp ON u.id = ubp.user_id
            WHERE ubp.read_status = 'READ'
            GROUP BY u.id, u.username
        """)
        clear_gauge_metrics(booklore_user_books_finished)
        for row in cursor.fetchall():
            booklore_user_books_finished.labels(user=row['username']).set(row['count'])

        # Average progress per user
        cursor.execute("""
            SELECT u.username,
                   AVG(GREATEST(
                       COALESCE(ubp.pdf_progress_percent, 0),
                       COALESCE(ubp.epub_progress_percent, 0),
                       COALESCE(ubp.cbx_progress_percent, 0),
                       COALESCE(ubp.koreader_progress_percent, 0)
                   )) as avg_progress
            FROM users u
            JOIN user_book_progress ubp ON u.id = ubp.user_id
            GROUP BY u.id, u.username
        """)
        clear_gauge_metrics(booklore_user_average_progress)
        for row in cursor.fetchall():
            if row['avg_progress'] is not None:
                booklore_user_average_progress.labels(user=row['username']).set(row['avg_progress'])

        # Books rated
        cursor.execute("""
            SELECT u.username, COUNT(*) as count, AVG(ubp.personal_rating) as avg_rating
            FROM users u
            JOIN user_book_progress ubp ON u.id = ubp.user_id
            WHERE ubp.personal_rating IS NOT NULL
            GROUP BY u.id, u.username
        """)
        clear_gauge_metrics(booklore_user_books_rated)
        clear_gauge_metrics(booklore_user_average_rating)
        for row in cursor.fetchall():
            booklore_user_books_rated.labels(user=row['username']).set(row['count'])
            if row['avg_rating']:
                booklore_user_average_rating.labels(user=row['username']).set(row['avg_rating'])

        # Books by progress range
        cursor.execute("""
            SELECT u.username,
                   CASE
                       WHEN COALESCE(ubp.koreader_progress_percent, ubp.epub_progress_percent, ubp.pdf_progress_percent, ubp.cbx_progress_percent, 0) = 0 THEN '0%'
                       WHEN COALESCE(ubp.koreader_progress_percent, ubp.epub_progress_percent, ubp.pdf_progress_percent, ubp.cbx_progress_percent, 0) <= 0.25 THEN '1-25%'
                       WHEN COALESCE(ubp.koreader_progress_percent, ubp.epub_progress_percent, ubp.pdf_progress_percent, ubp.cbx_progress_percent, 0) <= 0.50 THEN '26-50%'
                       WHEN COALESCE(ubp.koreader_progress_percent, ubp.epub_progress_percent, ubp.pdf_progress_percent, ubp.cbx_progress_percent, 0) <= 0.75 THEN '51-75%'
                       WHEN COALESCE(ubp.koreader_progress_percent, ubp.epub_progress_percent, ubp.pdf_progress_percent, ubp.cbx_progress_percent, 0) < 1.0 THEN '76-99%'
                       ELSE '100%'
                   END as progress_range,
                   COUNT(*) as count
            FROM users u
            JOIN user_book_progress ubp ON u.id = ubp.user_id
            GROUP BY u.id, u.username, progress_range
        """)
        clear_gauge_metrics(booklore_user_books_by_progress_range)
        for row in cursor.fetchall():
            booklore_user_books_by_progress_range.labels(user=row['username'], progress_range=row['progress_range']).set(row['count'])

        # Books by personal rating
        cursor.execute("""
            SELECT u.username, ubp.personal_rating as rating, COUNT(*) as count
            FROM users u
            JOIN user_book_progress ubp ON u.id = ubp.user_id
            WHERE ubp.personal_rating IS NOT NULL
            GROUP BY u.id, u.username, ubp.personal_rating
        """)
        clear_gauge_metrics(booklore_user_books_by_rating)
        for row in cursor.fetchall():
            booklore_user_books_by_rating.labels(user=row['username'], rating=str(row['rating'])).set(row['count'])

        # =====================================================================
        # READING SESSION METRICS
        # =====================================================================

        # Total reading sessions
        cursor.execute("SELECT COUNT(*) as count FROM reading_sessions")
        booklore_reading_sessions_total.set(cursor.fetchone()['count'])

        # Total reading time per user
        cursor.execute("""
            SELECT u.username, COALESCE(SUM(rs.duration_seconds), 0) as total_seconds
            FROM users u
            LEFT JOIN reading_sessions rs ON u.id = rs.user_id
            GROUP BY u.id, u.username
        """)
        clear_gauge_metrics(booklore_reading_time_total_seconds)
        for row in cursor.fetchall():
            booklore_reading_time_total_seconds.labels(user=row['username']).set(row['total_seconds'])

        # Reading sessions by date (last 30 days)
        cursor.execute("""
            SELECT u.username, DATE(rs.start_time) as date,
                   COUNT(*) as sessions,
                   SUM(rs.duration_seconds) as total_seconds,
                   SUM(rs.progress_delta) as total_progress
            FROM users u
            JOIN reading_sessions rs ON u.id = rs.user_id
            WHERE rs.start_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY u.id, u.username, DATE(rs.start_time)
        """)
        clear_gauge_metrics(booklore_reading_sessions_by_date)
        clear_gauge_metrics(booklore_reading_time_by_date)
        clear_gauge_metrics(booklore_reading_progress_by_date)
        for row in cursor.fetchall():
            date_str = row['date'].strftime('%Y-%m-%d')
            booklore_reading_sessions_by_date.labels(user=row['username'], date=date_str).set(row['sessions'])
            booklore_reading_time_by_date.labels(user=row['username'], date=date_str).set(row['total_seconds'])
            booklore_reading_progress_by_date.labels(user=row['username'], date=date_str).set(row['total_progress'] or 0)

        # Reading sessions by book type
        cursor.execute("""
            SELECT u.username, rs.book_type, COUNT(*) as sessions, SUM(rs.duration_seconds) as total_seconds
            FROM users u
            JOIN reading_sessions rs ON u.id = rs.user_id
            GROUP BY u.id, u.username, rs.book_type
        """)
        clear_gauge_metrics(booklore_reading_sessions_by_book_type)
        clear_gauge_metrics(booklore_reading_time_by_book_type)
        for row in cursor.fetchall():
            booklore_reading_sessions_by_book_type.labels(user=row['username'], book_type=row['book_type']).set(row['sessions'])
            booklore_reading_time_by_book_type.labels(user=row['username'], book_type=row['book_type']).set(row['total_seconds'])

        # Reading time by category/genre (top 15)
        cursor.execute("""
            SELECT u.username, c.name as category, SUM(rs.duration_seconds) as total_seconds
            FROM users u
            JOIN reading_sessions rs ON u.id = rs.user_id
            JOIN book b ON rs.book_id = b.id
            JOIN book_metadata bm ON b.id = bm.book_id
            JOIN book_metadata_category_mapping bcm ON bm.book_id = bcm.book_id
            JOIN category c ON bcm.category_id = c.id
            GROUP BY u.id, u.username, c.name
            ORDER BY total_seconds DESC
            LIMIT 15
        """)
        clear_gauge_metrics(booklore_reading_time_by_category)
        for row in cursor.fetchall():
            booklore_reading_time_by_category.labels(user=row['username'], category=row['category']).set(row['total_seconds'])

        # =====================================================================
        # READING STREAKS AND HABITS
        # =====================================================================

        # Get users for streak calculation
        cursor.execute("SELECT id, username FROM users")
        users = cursor.fetchall()

        clear_gauge_metrics(booklore_current_reading_streak_days)
        clear_gauge_metrics(booklore_longest_reading_streak_days)
        clear_gauge_metrics(booklore_days_read_this_month)
        clear_gauge_metrics(booklore_days_read_this_year)
        clear_gauge_metrics(booklore_average_session_duration_seconds)

        for user in users:
            # Get distinct reading days ordered
            cursor.execute("""
                SELECT DISTINCT DATE(start_time) as read_date
                FROM reading_sessions
                WHERE user_id = %s
                ORDER BY read_date DESC
            """, (user['id'],))
            read_dates = [row['read_date'] for row in cursor.fetchall()]

            # Calculate current streak
            current_streak = 0
            if read_dates:
                today = datetime.now().date()
                expected_date = today
                for read_date in read_dates:
                    if read_date == expected_date or read_date == expected_date - timedelta(days=1):
                        current_streak += 1
                        expected_date = read_date - timedelta(days=1)
                    else:
                        break

            booklore_current_reading_streak_days.labels(user=user['username']).set(current_streak)

            # Calculate longest streak
            longest_streak = 0
            if read_dates:
                read_dates_asc = sorted(read_dates)
                streak = 1
                for i in range(1, len(read_dates_asc)):
                    if read_dates_asc[i] - read_dates_asc[i-1] == timedelta(days=1):
                        streak += 1
                    else:
                        longest_streak = max(longest_streak, streak)
                        streak = 1
                longest_streak = max(longest_streak, streak)

            booklore_longest_reading_streak_days.labels(user=user['username']).set(longest_streak)

            # Days read this month
            cursor.execute("""
                SELECT COUNT(DISTINCT DATE(start_time)) as days
                FROM reading_sessions
                WHERE user_id = %s AND YEAR(start_time) = YEAR(CURDATE()) AND MONTH(start_time) = MONTH(CURDATE())
            """, (user['id'],))
            result = cursor.fetchone()
            booklore_days_read_this_month.labels(user=user['username']).set(result['days'] if result else 0)

            # Days read this year
            cursor.execute("""
                SELECT COUNT(DISTINCT DATE(start_time)) as days
                FROM reading_sessions
                WHERE user_id = %s AND YEAR(start_time) = YEAR(CURDATE())
            """, (user['id'],))
            result = cursor.fetchone()
            booklore_days_read_this_year.labels(user=user['username']).set(result['days'] if result else 0)

            # Average session duration
            cursor.execute("""
                SELECT AVG(duration_seconds) as avg_duration
                FROM reading_sessions
                WHERE user_id = %s
            """, (user['id'],))
            result = cursor.fetchone()
            if result and result['avg_duration']:
                booklore_average_session_duration_seconds.labels(user=user['username']).set(result['avg_duration'])

        # Reading sessions by hour of day
        cursor.execute("""
            SELECT u.username, HOUR(rs.start_time) as hour, COUNT(*) as sessions
            FROM users u
            JOIN reading_sessions rs ON u.id = rs.user_id
            GROUP BY u.id, u.username, HOUR(rs.start_time)
        """)
        clear_gauge_metrics(booklore_reading_sessions_by_hour)
        for row in cursor.fetchall():
            booklore_reading_sessions_by_hour.labels(user=row['username'], hour=str(row['hour']).zfill(2)).set(row['sessions'])

        # Reading sessions by weekday
        cursor.execute("""
            SELECT u.username, DAYNAME(rs.start_time) as weekday, COUNT(*) as sessions
            FROM users u
            JOIN reading_sessions rs ON u.id = rs.user_id
            GROUP BY u.id, u.username, DAYOFWEEK(rs.start_time), DAYNAME(rs.start_time)
            ORDER BY DAYOFWEEK(rs.start_time)
        """)
        clear_gauge_metrics(booklore_reading_sessions_by_weekday)
        for row in cursor.fetchall():
            booklore_reading_sessions_by_weekday.labels(user=row['username'], weekday=row['weekday']).set(row['sessions'])

        # =====================================================================
        # BOOKS FINISHED OVER TIME
        # =====================================================================

        # Books finished by month (last 12 months)
        cursor.execute("""
            SELECT u.username, DATE_FORMAT(ubp.date_finished, '%Y-%m') as ym, COUNT(*) as count
            FROM users u
            JOIN user_book_progress ubp ON u.id = ubp.user_id
            WHERE ubp.date_finished IS NOT NULL
              AND ubp.date_finished >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY u.id, u.username, DATE_FORMAT(ubp.date_finished, '%Y-%m')
        """)
        clear_gauge_metrics(booklore_books_finished_by_month)
        for row in cursor.fetchall():
            booklore_books_finished_by_month.labels(user=row['username'], ym=row['ym']).set(row['count'])

        # Books finished this year
        cursor.execute("""
            SELECT u.username, COUNT(*) as count
            FROM users u
            JOIN user_book_progress ubp ON u.id = ubp.user_id
            WHERE ubp.date_finished IS NOT NULL AND YEAR(ubp.date_finished) = YEAR(CURDATE())
            GROUP BY u.id, u.username
        """)
        clear_gauge_metrics(booklore_books_finished_this_year)
        for row in cursor.fetchall():
            booklore_books_finished_this_year.labels(user=row['username']).set(row['count'])

        # Books finished this month
        cursor.execute("""
            SELECT u.username, COUNT(*) as count
            FROM users u
            JOIN user_book_progress ubp ON u.id = ubp.user_id
            WHERE ubp.date_finished IS NOT NULL
              AND YEAR(ubp.date_finished) = YEAR(CURDATE())
              AND MONTH(ubp.date_finished) = MONTH(CURDATE())
            GROUP BY u.id, u.username
        """)
        clear_gauge_metrics(booklore_books_finished_this_month)
        for row in cursor.fetchall():
            booklore_books_finished_this_month.labels(user=row['username']).set(row['count'])

        # =====================================================================
        # RECENT ACTIVITY
        # =====================================================================

        # Last read timestamp
        cursor.execute("""
            SELECT u.username, MAX(rs.end_time) as last_read
            FROM users u
            LEFT JOIN reading_sessions rs ON u.id = rs.user_id
            GROUP BY u.id, u.username
        """)
        clear_gauge_metrics(booklore_last_read_timestamp)
        for row in cursor.fetchall():
            if row['last_read']:
                booklore_last_read_timestamp.labels(user=row['username']).set(row['last_read'].timestamp())

        # Books read last 7 days
        cursor.execute("""
            SELECT u.username, COUNT(DISTINCT rs.book_id) as count
            FROM users u
            JOIN reading_sessions rs ON u.id = rs.user_id
            WHERE rs.start_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY u.id, u.username
        """)
        clear_gauge_metrics(booklore_books_read_last_7_days)
        for row in cursor.fetchall():
            booklore_books_read_last_7_days.labels(user=row['username']).set(row['count'])

        # Reading time last 7 days
        cursor.execute("""
            SELECT u.username, COALESCE(SUM(rs.duration_seconds), 0) as total_seconds
            FROM users u
            LEFT JOIN reading_sessions rs ON u.id = rs.user_id AND rs.start_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY u.id, u.username
        """)
        clear_gauge_metrics(booklore_reading_time_last_7_days_seconds)
        for row in cursor.fetchall():
            booklore_reading_time_last_7_days_seconds.labels(user=row['username']).set(row['total_seconds'])

        # Reading time last 30 days
        cursor.execute("""
            SELECT u.username, COALESCE(SUM(rs.duration_seconds), 0) as total_seconds
            FROM users u
            LEFT JOIN reading_sessions rs ON u.id = rs.user_id AND rs.start_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY u.id, u.username
        """)
        clear_gauge_metrics(booklore_reading_time_last_30_days_seconds)
        for row in cursor.fetchall():
            booklore_reading_time_last_30_days_seconds.labels(user=row['username']).set(row['total_seconds'])

        # =====================================================================
        # KOREADER SYNC METRICS
        # =====================================================================

        # KOReader synced books
        cursor.execute("""
            SELECT u.username, ubp.koreader_device, COUNT(*) as count
            FROM users u
            JOIN user_book_progress ubp ON u.id = ubp.user_id
            WHERE ubp.koreader_device IS NOT NULL
            GROUP BY u.id, u.username, ubp.koreader_device
        """)
        clear_gauge_metrics(booklore_koreader_synced_books)
        for row in cursor.fetchall():
            booklore_koreader_synced_books.labels(user=row['username'], device=row['koreader_device']).set(row['count'])

        # Last KOReader sync
        cursor.execute("""
            SELECT u.username, MAX(ubp.koreader_last_sync_time) as last_sync
            FROM users u
            JOIN user_book_progress ubp ON u.id = ubp.user_id
            WHERE ubp.koreader_last_sync_time IS NOT NULL
            GROUP BY u.id, u.username
        """)
        clear_gauge_metrics(booklore_koreader_last_sync_timestamp)
        for row in cursor.fetchall():
            if row['last_sync']:
                booklore_koreader_last_sync_timestamp.labels(user=row['username']).set(row['last_sync'].timestamp())

        # =====================================================================
        # SCRAPE METRICS
        # =====================================================================

        booklore_last_scrape.set(time.time())
        duration = time.time() - start_time
        booklore_scrape_duration.set(duration)

        cursor.close()
        conn.close()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Metrics collected successfully in {duration:.2f}s")

    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error collecting metrics: {e}")
        booklore_scrape_errors.inc()


def main():
    print(f"Starting BookLore Prometheus Exporter on port {EXPORTER_PORT}")
    print(f"Scrape interval: {SCRAPE_INTERVAL} seconds")
    print(f"Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")

    # Start HTTP server
    start_http_server(EXPORTER_PORT)
    print(f"Metrics available at http://0.0.0.0:{EXPORTER_PORT}/metrics")

    # Collect metrics periodically
    while True:
        collect_metrics()
        time.sleep(SCRAPE_INTERVAL)


if __name__ == '__main__':
    main()
