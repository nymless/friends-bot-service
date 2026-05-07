import sqlite3
from datetime import datetime

from friends_bot_service.enums import CountCol, DateCol, GameType


class DBHandler:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self) -> None:
        cur = self.conn.cursor()

        # Create tables
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1 NOT NULL,
            PRIMARY KEY(chat_id, user_id)
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            win_count INTEGER DEFAULT 0 NOT NULL,
            last_win TEXT,
            lose_count INTEGER DEFAULT 0 NOT NULL,
            last_lose TEXT,
            PRIMARY KEY(chat_id, user_id)
        )""")

        # Create utility indexes "One winner per day" to ensure data integrity
        # by preventing possible race conditions
        cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS one_winner_per_day
            ON stats(chat_id, last_win)
            WHERE last_win IS NOT NULL
        """)
        cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS one_loser_per_day
            ON stats(chat_id, last_lose)
            WHERE last_lose IS NOT NULL
        """)
        self.conn.commit()

    def register_user(
        self, chat_id: int, user_id: int, username: str | None, full_name: str
    ) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO users (chat_id, user_id, username, full_name, is_active) 
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET 
                username=excluded.username, 
                full_name=excluded.full_name,
                is_active=1
            """,
            (chat_id, user_id, username, full_name),
        )
        self.conn.commit()

    def unregister_user(self, chat_id: int, user_id: int) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE users SET is_active = 0 WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def is_already_runned(self, chat_id: int, game_type: GameType):
        """Check if there was already a winner today"""
        configs = {
            GameType.WINNER: DateCol.LAST_WIN,
            GameType.LOSER: DateCol.LAST_LOSE,
        }
        column = configs[game_type]
        today = datetime.now().strftime("%Y-%m-%d")
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT user_id FROM stats WHERE chat_id = ? AND {column} = ?",
            (chat_id, today),
        )
        return cur.fetchone()

    def get_players(self, chat_id: int):
        """Get a list of players, except for those who have already won another game"""
        today = datetime.now().strftime("%Y-%m-%d")

        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT user_id, full_name FROM users
            WHERE chat_id = ? AND is_active = 1 AND user_id NOT IN (
                SELECT user_id FROM stats WHERE chat_id = ?
                    AND ({DateCol.LAST_WIN} = ? OR {DateCol.LAST_LOSE} = ?)
            )
            """,
            (chat_id, chat_id, today, today),
        )
        return cur.fetchall()

    def set_winner(self, chat_id: int, user_id: int, game_type: GameType) -> bool:
        configs = {
            GameType.WINNER: (CountCol.WIN_COUNT, DateCol.LAST_WIN),
            GameType.LOSER: (CountCol.LOSE_COUNT, DateCol.LAST_LOSE),
        }
        count_col, date_col = configs[game_type]
        today = datetime.now().strftime("%Y-%m-%d")

        cur = self.conn.cursor()
        try:
            # If there is no record, a new one is set with a counter of 1
            # If a record exists, the counter is incremented and a new date is set
            cur.execute(
                f"""INSERT INTO stats (chat_id, user_id, {count_col}, {date_col}) 
                    VALUES (?, ?, 1, ?) 
                    ON CONFLICT(chat_id, user_id) DO UPDATE SET
                        {count_col} = {count_col} + 1,
                        {date_col} = ?
                """,
                (chat_id, user_id, today, today),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_statistics(self, chat_id: int, game_type: GameType):
        """Returns a list of tuples (full_name, count) for a specific game"""
        configs = {
            GameType.WINNER: CountCol.WIN_COUNT,
            GameType.LOSER: CountCol.LOSE_COUNT,
        }
        column = configs[game_type]

        cur = self.conn.cursor()
        # Select only with a positive score and sort in descending order
        cur.execute(
            f"""SELECT users.full_name, stats.{column} FROM stats
                JOIN users ON stats.user_id = users.user_id
                AND stats.chat_id = users.chat_id
                WHERE stats.chat_id = ? AND stats.{column} > 0
                ORDER BY stats.{column} DESC
                """,
            (chat_id,),
        )
        return cur.fetchall()

    def close(self):
        self.conn.close()
