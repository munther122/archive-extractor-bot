import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        self.path = str(path)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init()

    def init(self):
        with self.lock, self.conn:
            self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, date_joined TEXT NOT NULL, last_activity TEXT NOT NULL, files_count INTEGER DEFAULT 0, archives_count INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS archives(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL, path TEXT NOT NULL, size INTEGER DEFAULT 0, file_count INTEGER DEFAULT 0, folder_count INTEGER DEFAULT 0, created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY AUTOINCREMENT, archive_id INTEGER NOT NULL, user_id INTEGER NOT NULL, rel_path TEXT NOT NULL, abs_path TEXT NOT NULL, size INTEGER DEFAULT 0, is_dir INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS downloads(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT, status TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS required_channels(id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id INTEGER NOT NULL UNIQUE, username TEXT, title TEXT, invite_link TEXT, enabled INTEGER DEFAULT 1, date_added TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            CREATE INDEX IF NOT EXISTS idx_files_archive ON files(archive_id);
            CREATE INDEX IF NOT EXISTS idx_files_user ON files(user_id);
            ''')

    def upsert_user(self, user_id, username, first_name):
        with self.lock, self.conn:
            self.conn.execute('''INSERT INTO users(user_id,username,first_name,date_joined,last_activity) VALUES(?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name,last_activity=excluded.last_activity''', (user_id, username, first_name, now(), now()))

    def user(self, user_id):
        return self.conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()

    def set_banned(self, user_id, banned):
        with self.lock, self.conn: self.conn.execute("UPDATE users SET is_banned=? WHERE user_id=?", (int(banned), user_id))

    def inc_user(self, user_id, field):
        if field not in ("files_count", "archives_count"): raise ValueError("bad counter")
        with self.lock, self.conn: self.conn.execute(f"UPDATE users SET {field}={field}+1 WHERE user_id=?", (user_id,))

    def add_archive(self, user_id, name, path, size, file_count, folder_count, expires_at):
        with self.lock, self.conn:
            cur=self.conn.execute("INSERT INTO archives(user_id,name,path,size,file_count,folder_count,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?)", (user_id,name,path,size,file_count,folder_count,now(),expires_at))
            return cur.lastrowid

    def add_file(self, archive_id, user_id, rel_path, abs_path, size, is_dir=0):
        with self.lock, self.conn: self.conn.execute("INSERT INTO files(archive_id,user_id,rel_path,abs_path,size,is_dir) VALUES(?,?,?,?,?,?)", (archive_id,user_id,rel_path,abs_path,size,is_dir))

    def archive(self, archive_id, user_id=None):
        q="SELECT * FROM archives WHERE id=?"; args=[archive_id]
        if user_id is not None: q += " AND user_id=?"; args.append(user_id)
        return self.conn.execute(q,args).fetchone()

    def archives(self, user_id): return self.conn.execute("SELECT * FROM archives WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
    def files(self, archive_id, user_id, prefix=""):
        return self.conn.execute("SELECT * FROM files WHERE archive_id=? AND user_id=? AND rel_path LIKE ? ORDER BY is_dir DESC,rel_path", (archive_id,user_id,prefix+"%" )).fetchall()
    def file(self, file_id, user_id): return self.conn.execute("SELECT * FROM files WHERE id=? AND user_id=?", (file_id,user_id)).fetchone()
    def search_files(self, archive_id,user_id,text): return self.conn.execute("SELECT * FROM files WHERE archive_id=? AND user_id=? AND rel_path LIKE ? ORDER BY rel_path", (archive_id,user_id,f"%{text}%")).fetchall()

    def delete_archive(self, archive_id, user_id):
        with self.lock, self.conn:
            row=self.archive(archive_id,user_id)
            if not row: return None
            self.conn.execute("DELETE FROM files WHERE archive_id=?",(archive_id,)); self.conn.execute("DELETE FROM archives WHERE id=?",(archive_id,)); return row

    def channels(self, enabled_only=False):
        q="SELECT * FROM required_channels" + (" WHERE enabled=1" if enabled_only else "") + " ORDER BY id"
        return self.conn.execute(q).fetchall()
    def add_channel(self, channel_id, username, title, invite_link):
        with self.lock,self.conn:
            self.conn.execute("INSERT OR REPLACE INTO required_channels(channel_id,username,title,invite_link,enabled,date_added) VALUES(?,?,?,?,1,?)",(channel_id,username,title,invite_link,now()))
    def channel(self, cid): return self.conn.execute("SELECT * FROM required_channels WHERE id=?",(cid,)).fetchone()
    def toggle_channel(self,cid):
        with self.lock,self.conn: self.conn.execute("UPDATE required_channels SET enabled=1-enabled WHERE id=?",(cid,))
    def delete_channel(self,cid):
        with self.lock,self.conn: self.conn.execute("DELETE FROM required_channels WHERE id=?",(cid,))
    def stats(self):
        q=lambda s:self.conn.execute(s).fetchone()[0]
        return {"users":q("SELECT COUNT(*) FROM users"),"active":q("SELECT COUNT(*) FROM users WHERE last_activity>=datetime('now','-7 days')"),"banned":q("SELECT COUNT(*) FROM users WHERE is_banned=1"),"archives":q("SELECT COUNT(*) FROM archives"),"files":q("SELECT COUNT(*) FROM files WHERE is_dir=0"),"storage":q("SELECT COALESCE(SUM(size),0) FROM files"),"downloads":q("SELECT COUNT(*) FROM downloads"),"video":q("SELECT COUNT(*) FROM downloads WHERE kind='video'"),"audio":q("SELECT COUNT(*) FROM downloads WHERE kind='audio'")}
    def log_job(self,user_id,kind,status):
        with self.lock,self.conn: self.conn.execute("INSERT INTO downloads(user_id,kind,status,created_at) VALUES(?,?,?,?)",(user_id,kind,status,now()))
    def cleanup_expired(self):
        rows=self.conn.execute("SELECT * FROM archives WHERE expires_at < ?",(now(),)).fetchall()
        with self.lock,self.conn:
            for r in rows: self.conn.execute("DELETE FROM files WHERE archive_id=?",(r["id"],)); self.conn.execute("DELETE FROM archives WHERE id=?",(r["id"],))
        return rows

    def users(self, mode="all"):
        where={"active":"WHERE last_activity>=datetime('now','-7 days')","banned":"WHERE is_banned=1"}.get(mode,"")
        return self.conn.execute(f"SELECT * FROM users {where} ORDER BY user_id DESC LIMIT 100").fetchall()
