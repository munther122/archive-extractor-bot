from bot.database import Database

def test_users_channels_and_archive(tmp_path):
    db=Database(tmp_path/'db.sqlite3'); db.upsert_user(7,'user','اسم')
    assert db.user(7)['username']=='user'
    db.set_banned(7,1); assert db.user(7)['is_banned']==1
    db.add_channel(-100,'@chan','قناة','https://t.me/chan'); assert len(db.channels())==1
    aid=db.add_archive(7,'a.zip',str(tmp_path),10,1,0,'2999-01-01T00:00:00'); db.add_file(aid,7,'x.txt',str(tmp_path/'x.txt'),10)
    assert db.archive(aid,7)['file_count']==1 and db.file(1,7)['rel_path']=='x.txt'
    assert db.stats()['archives']==1
