import asyncio, os, re, shutil, tempfile
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters
from telegram.error import TelegramError
from bot.config import settings
from bot.database import Database
from bot.services.archive_service import ArchiveService
from bot.services.media_service import MediaService
from bot.services.subscription_service import SubscriptionService
from bot.keyboards.main import main_menu, home, back_home, file_actions
from bot.keyboards.admin import admin_menu, channel_menu, channel_actions, user_list, user_actions
from bot.utils.logger import setup_logging

setup_logging(); settings.prepare(); db=Database(settings.db_path); archives=ArchiveService(settings); media=MediaService(settings); subs=SubscriptionService(db,settings)

HELP='''❓ <b>شرح البوت</b>\n\n📦 أرسل ZIP أو RAR أو 7Z أو TAR.GZ كملف مباشر.\n🔎 بعد الفك يمكنك تصفح المجلدات والبحث عن ملف محدد وإرساله وحده.\n📤 لا يتم إرسال كل الملفات تلقائيًا.\n🎬 يمكن تحويل الفيديو واستخراج الصوت عند توفر FFmpeg.\n🧹 الملفات المؤقتة محفوظة في مجلد خاص بك وتحذف تلقائيًا بعد مدة الانتهاء.\n🛡️ توجد حماية من Zip Slip والروابط الرمزية والأرشيفات الضخمة.\n\nحدود Telegram نفسها قد تمنع الملفات الكبيرة.'''

def is_admin(uid): return uid in settings.admin_ids

def user_allowed(update):
    u=update.effective_user; row=db.user(u.id); return not row or not row['is_banned']

async def guard(update, context):
    u=update.effective_user
    if not user_allowed(update):
        await (update.callback_query.message if update.callback_query else update.message).reply_text('🚫 تم إيقاف حسابك عن استخدام البوت.')
        return False
    missing=await subs.missing(context.bot,u.id)
    if missing:
        rows=[]
        for c in missing:
            link=c['invite_link'] or (f"https://t.me/{c['username'].lstrip('@')}" if c['username'] else None)
            if link: rows.append([InlineKeyboardButton(f'📲 الاشتراك في {c["title"] or c["username"] or "القناة"}',url=link)])
        rows.append([InlineKeyboardButton('✅ تحقق من الاشتراك',callback_data='checksub')])
        target=update.callback_query.message if update.callback_query else update.message
        await target.reply_text('🔒 يجب الاشتراك في القنوات التالية لاستخدام البوت:',reply_markup=InlineKeyboardMarkup(rows))
        return False
    return True

async def start(update, context):
    u=update.effective_user; db.upsert_user(u.id,u.username,u.first_name)
    if not user_allowed(update): return await update.message.reply_text('🚫 تم إيقاف حسابك عن استخدام البوت.')
    if not await guard(update,context): return
    await update.message.reply_text(f'أهلًا {u.first_name or "بك"} 👋\nأرسل ملفًا مضغوطًا وسأفكّه لك، أو اختر من القائمة:',reply_markup=main_menu(is_admin(u.id)))

async def help_cmd(update,context):
    if await guard(update,context): await update.message.reply_text(HELP,parse_mode='HTML',reply_markup=home())

async def help_cb(update,context):
    q=update.callback_query; await q.answer()
    if await guard(update,context): await q.edit_message_text(HELP,parse_mode='HTML',reply_markup=home())

async def home_cb(update,context):
    q=update.callback_query; await q.answer()
    if await guard(update,context): await q.edit_message_text('🏠 القائمة الرئيسية',reply_markup=main_menu(is_admin(q.from_user.id)))

async def files_cb(update,context):
    q=update.callback_query; await q.answer()
    if not await guard(update,context): return
    await q.edit_message_text('📦 إدارة الملفات\n\nأرسل أرشيفًا كـ Document لبدء المعالجة، أو اختر ملفًا محفوظًا:',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('📋 ملفاتي',callback_data='myfiles')],[InlineKeyboardButton('🏠 الرئيسية',callback_data='home')]]))

async def document(update,context):
    u=update.effective_user; db.upsert_user(u.id,u.username,u.first_name)
    if not await guard(update,context): return
    d=update.message.document
    if d.file_size and d.file_size>settings.max_file_size: return await update.message.reply_text(f'الملف أكبر من الحد ({settings.max_file_size//1024//1024} MB).')
    ext=Path(d.file_name or '').suffix.lower()
    if ext not in ('.zip','.rar','.7z','.tar','.gz','.bz2','.xz') and not (d.file_name or '').lower().endswith('.tgz'):
        return await update.message.reply_text('أرسل ZIP أو RAR أو 7Z أو TAR.GZ كـ Document.')
    job=f'{u.id}-{datetime.utcnow().strftime("%Y%m%d%H%M%S%f")}'; root=settings.data_dir/'users'/str(u.id)/job; root.mkdir(parents=True,exist_ok=True)
    src=root/(d.file_name or 'archive.bin'); out=root/'extracted'; msg=await update.message.reply_text('⏳ طلبك قيد المعالجة...')
    db.log_job(u.id,'archive','running')
    try:
        await update.message.chat.send_action(ChatAction.UPLOAD_DOCUMENT); f=await context.bot.get_file(d.file_id); await f.download_to_drive(custom_path=src)
        fc,dirs,total=await asyncio.to_thread(archives.extract,src,out)
        expires=(datetime.utcnow()+timedelta(hours=settings.retention_hours)).isoformat(timespec='seconds'); aid=db.add_archive(u.id,d.file_name or 'archive',str(root),d.file_size or 0,fc,dirs,expires)
        for p in out.rglob('*'):
            db.add_file(aid,u.id,str(p.relative_to(out)),str(p),p.stat().st_size,int(p.is_dir()))
        db.inc_user(u.id,'archives_count'); db.log_job(u.id,'archive','done')
        await msg.edit_text(f'📦 <b>{d.file_name}</b>\n📊 الحجم: {d.file_size or 0} bytes\n📄 الملفات: {fc}\n📂 المجلدات: {dirs}',parse_mode='HTML',reply_markup=file_actions(aid))
    except Exception as e:
        db.log_job(u.id,'archive','failed'); shutil.rmtree(root,ignore_errors=True); await msg.edit_text(f'❌ تعذر فك الأرشيف بأمان: {str(e)[:250]}')

async def myfiles(update,context):
    q=update.callback_query; await q.answer()
    if not await guard(update,context): return
    rows=[]
    for a in db.archives(q.from_user.id): rows.append([InlineKeyboardButton(f'📦 {a["name"]} ({a["file_count"]})',callback_data=f'archive:{a["id"]}')])
    rows.append([InlineKeyboardButton('🏠 الرئيسية',callback_data='home')]); await q.edit_message_text('📋 ملفاتك المحفوظة:',reply_markup=InlineKeyboardMarkup(rows))

async def archive_view(update,context):
    q=update.callback_query; await q.answer(); aid=int(q.data.split(':')[1]); a=db.archive(aid,q.from_user.id)
    if not a: return await q.edit_message_text('الملف غير موجود.',reply_markup=home())
    await q.edit_message_text(f'📦 {a["name"]}\n📄 الملفات: {a["file_count"]}\n📂 المجلدات: {a["folder_count"]}',reply_markup=file_actions(aid))

async def browse(update,context):
    q=update.callback_query; await q.answer(); _,aid,*parts=q.data.split(':'); prefix=parts[0]+'/' if parts else ''; rows=[]; seen=set()
    for f in db.files(int(aid),q.from_user.id,prefix):
        rest=f['rel_path'][len(prefix):]; first=rest.split('/')[0]
        if '/' in rest or f['is_dir']:
            if first in seen: continue
            seen.add(first); rows.append([InlineKeyboardButton('📂 '+first,callback_data=f'browse:{aid}:{prefix}{first}')])
        else: rows.append([InlineKeyboardButton('📄 '+first,callback_data=f'file:{f["id"]}')])
    if prefix: rows.append([InlineKeyboardButton('⬅️ مجلد سابق',callback_data=f'browse:{aid}:')])
    rows += [[InlineKeyboardButton('🔍 بحث',callback_data=f'search:{aid}')],[InlineKeyboardButton('🏠 الرئيسية',callback_data='home')]]
    await q.edit_message_text('🔎 تصفح الملفات' + (f'\n📂 {prefix}' if prefix else ''),reply_markup=InlineKeyboardMarkup(rows))

async def file_view(update,context):
    q=update.callback_query; await q.answer(); f=db.file(int(q.data.split(':')[1]),q.from_user.id)
    if not f: return await q.edit_message_text('الملف غير موجود.',reply_markup=home())
    rows=[[InlineKeyboardButton('📤 إرسال الملف',callback_data=f'sendfile:{f["id"]}'),InlineKeyboardButton('🗑️ حذف',callback_data=f'delfile:{f["id"]}')],[InlineKeyboardButton('⬅️ رجوع',callback_data=f'browse:{f["archive_id"]}'),InlineKeyboardButton('🏠 الرئيسية',callback_data='home')]]
    await q.edit_message_text(f'📄 {f["rel_path"]}\nالحجم: {f["size"]} bytes\nالمسار: {f["rel_path"]}',reply_markup=InlineKeyboardMarkup(rows))

async def send_file(update,context):
    q=update.callback_query; await q.answer(); f=db.file(int(q.data.split(':')[1]),q.from_user.id)
    if not f or f['is_dir'] or f['size']>settings.max_single_output: return await q.message.reply_text('الملف غير صالح أو أكبر من حد الإرسال.')
    with open(f['abs_path'],'rb') as h: await q.message.reply_document(h,caption=f['rel_path'][:1024])
    db.inc_user(q.from_user.id,'files_count'); db.log_job(q.from_user.id,'download','done')

async def delete_file(update,context):
    q=update.callback_query; await q.answer(); f=db.file(int(q.data.split(':')[1]),q.from_user.id)
    if not f: return await q.edit_message_text('الملف غير موجود.',reply_markup=home())
    p=Path(f['abs_path'])
    if p.is_file(): p.unlink(missing_ok=True)
    with db.lock, db.conn:
        db.conn.execute('DELETE FROM files WHERE id=? AND user_id=?',(f['id'],q.from_user.id))
    await q.edit_message_text('🗑️ تم حذف الملف.',reply_markup=home())

async def extract_all(update,context):
    q=update.callback_query; await q.answer(); a=db.archive(int(q.data.split(':')[1]),q.from_user.id)
    if not a: return
    for f in db.files(a['id'],q.from_user.id):
        if not f['is_dir'] and f['size']<=settings.max_single_output:
            with open(f['abs_path'],'rb') as h: await q.message.reply_document(h,caption=f['rel_path'][:1024])
    db.log_job(q.from_user.id,'download','done')

async def delete_archive(update,context):
    q=update.callback_query; await q.answer(); a=db.delete_archive(int(q.data.split(':')[1]),q.from_user.id)
    if a: shutil.rmtree(a['path'],ignore_errors=True)
    await q.edit_message_text('🗑️ تم حذف الأرشيف وملفاته.',reply_markup=home())

async def search_start(update,context):
    q=update.callback_query; await q.answer(); context.user_data['state']='search'; context.user_data['archive_id']=int(q.data.split(':')[1]); await q.edit_message_text('🔍 أرسل جزءًا من اسم الملف للبحث:',reply_markup=back_home())

async def text_input(update,context):
    state=context.user_data.get('state'); text=update.message.text.strip()
    if state=='search':
        aid=context.user_data.get('archive_id'); rows=[]
        for f in db.search_files(aid,update.effective_user.id,text)[:50]: rows.append([InlineKeyboardButton('📄 '+f['rel_path'][:55],callback_data=f'file:{f["id"]}')])
        rows.append([InlineKeyboardButton('🏠 الرئيسية',callback_data='home')]); context.user_data.clear(); await update.message.reply_text(f'نتائج البحث عن: {text}',reply_markup=InlineKeyboardMarkup(rows))
    elif state=='channel_add' and is_admin(update.effective_user.id):
        await add_channel_text(update,context,text)
    elif state=='broadcast' and is_admin(update.effective_user.id):
        sent=failed=0
        for u in db.users():
            try:
                await context.bot.send_message(u['user_id'],text); sent+=1
            except TelegramError:
                failed+=1
        context.user_data.clear(); await update.message.reply_text(f'📢 اكتملت الإذاعة. نجح: {sent}، فشل: {failed}.',reply_markup=admin_menu())

async def add_channel_text(update,context,text):
    parts=text.split(); cid=None; username=''; invite=''
    for p in parts:
        if p.lstrip('-').isdigit(): cid=int(p)
        elif p.startswith('https://t.me/+'): invite=p
        elif p.startswith('@'): username=p
    if cid is None and username:
        try: chat=await context.bot.get_chat(username); cid=chat.id
        except TelegramError: return await update.message.reply_text('تعذر العثور على القناة. أرسل Channel ID أو تأكد أن البوت داخل القناة.')
    if cid is None: return await update.message.reply_text('أرسل مثلًا: -1001234567890 @channel أو رابط الدعوة الخاص.')
    try: chat=await context.bot.get_chat(cid); title=chat.title or ''; username=chat.username or username
    except TelegramError: title=''
    db.add_channel(cid,username,title,invite or (f'https://t.me/{username}' if username else '')); context.user_data.clear(); await update.message.reply_text('✅ تمت إضافة القناة. تأكد من جعل البوت مسؤولًا فيها.',reply_markup=admin_menu())

async def admin_cb(update,context):
    q=update.callback_query; await q.answer();
    if not is_admin(q.from_user.id): return await q.edit_message_text('غير مصرح.')
    action=q.data
    if action=='admin': return await q.edit_message_text('⚙️ لوحة الإدارة',reply_markup=admin_menu())
    if action=='adm:stats':
        s=db.stats(); txt='📊 الإحصائيات\n'+'\n'.join([f'{k}: {v}' for k,v in s.items()]); return await q.edit_message_text(txt,reply_markup=admin_menu())
    if action=='adm:users': return await q.edit_message_text(f'👥 إجمالي المستخدمين: {db.stats()["users"]}',reply_markup=user_list(db.users()))
    if action=='adm:channels': return await q.edit_message_text('📢 القنوات المطلوبة',reply_markup=channel_menu(db.channels()))
    if action=='adm:clean':
        rows=db.cleanup_expired()
        for r in rows: shutil.rmtree(r['path'],ignore_errors=True)
        return await q.edit_message_text(f'🧹 تم تنظيف {len(rows)} أرشيفًا منتهيًا.',reply_markup=admin_menu())
    if action=='adm:settings': return await q.edit_message_text(f'⚙️ الحدود\nMAX_FILE_SIZE={settings.max_file_size}\nMAX_EXTRACTED_SIZE={settings.max_extracted_size}\nMAX_FILES={settings.max_files}',reply_markup=admin_menu())
    if action=='adm:broadcast':
        context.user_data['state']='broadcast'; return await q.edit_message_text('📢 أرسل نص الرسالة التي تريد إذاعتها للمستخدمين.',reply_markup=admin_menu())
    if action.startswith('adm:user:'):
        uid=int(action.rsplit(':',1)[1]); u=db.user(uid)
        if not u: return await q.edit_message_text('المستخدم غير موجود.',reply_markup=admin_menu())
        return await q.edit_message_text(f'👤 ID: {u["user_id"]}\nUsername: @{u["username"] or "-"}\nالاسم: {u["first_name"] or "-"}\nالملفات: {u["files_count"]}\nالأرشيفات: {u["archives_count"]}\nالحالة: {"محظور" if u["is_banned"] else "نشط"}',reply_markup=user_actions(uid,u['is_banned']))
    if action.startswith('adm:ban:'):
        _,_,uid,banned=action.split(':'); db.set_banned(int(uid),int(banned)); u=db.user(int(uid))
        return await q.edit_message_text('تم تحديث حالة الحظر.',reply_markup=user_actions(int(uid),u['is_banned']))

async def channel_cb(update,context):
    q=update.callback_query; await q.answer();
    if not is_admin(q.from_user.id): return
    p=q.data.split(':')
    if p[1]=='add': context.user_data['state']='channel_add'; return await q.edit_message_text('➕ أرسل Channel ID أو @username أو رابط الدعوة الخاص بالقناة.')
    c=db.channel(int(p[2])) if len(p)>2 else None
    if not c: return
    if p[1]=='toggle': db.toggle_channel(c['id']); return await q.edit_message_text('تم تحديث حالة القناة.',reply_markup=channel_menu(db.channels()))
    if p[1]=='delete': db.delete_channel(c['id']); return await q.edit_message_text('تم حذف القناة.',reply_markup=channel_menu(db.channels()))
    await q.edit_message_text(f'{c["title"] or c["username"] or c["channel_id"]}\nالحالة: {"مفعلة" if c["enabled"] else "معطلة"}',reply_markup=channel_actions(c['id'],c['enabled']))

async def check_sub(update,context):
    q=update.callback_query; await q.answer(); missing=await subs.missing(context.bot,q.from_user.id)
    if missing: return await q.answer('❌ ما زال عليك الاشتراك في القنوات المطلوبة.',show_alert=True)
    await q.edit_message_text('✅ تم التحقق من اشتراكك.',reply_markup=main_menu(is_admin(q.from_user.id)))

async def cleanup(update,context):
    q=update.callback_query; await q.answer(); rows=db.archives(q.from_user.id); used=sum(r['size'] for r in rows); await q.edit_message_text(f'🧹 المساحة المستخدمة: {used} bytes\nيمكن حذف الأرشيف من صفحته.',reply_markup=home())

async def media_prompt(update,context):
    q=update.callback_query; await q.answer()
    if not await guard(update,context): return
    kind='audio' if q.data=='audio' else 'video'; context.user_data['media_kind']=kind; await q.edit_message_text('أرسل ملف الفيديو الآن:',reply_markup=home())

async def media_document(update,context):
    kind=context.user_data.pop('media_kind',None)
    if not kind: return await document(update,context)
    root=Path(tempfile.mkdtemp(prefix=f'{kind}-{update.effective_user.id}-',dir=settings.data_dir)); src=root/(update.message.document.file_name or 'input.bin')
    try:
        f=await context.bot.get_file(update.message.document.file_id); await f.download_to_drive(custom_path=src); out=await media.convert(src,kind)
        with out.open('rb') as h: await update.message.reply_document(h,caption='✅ تم التحويل')
        db.log_job(update.effective_user.id,kind,'done')
    except Exception as e: await update.message.reply_text(f'❌ {e}')
    finally: shutil.rmtree(root,ignore_errors=True)

async def media_or_archive(update,context):
    if context.user_data.get('media_kind'):
        await media_document(update,context)
    else:
        await document(update,context)

def build_app():
    if not settings.token: raise SystemExit('ضع BOT_TOKEN في .env')
    app=Application.builder().token(settings.token).concurrent_updates(True).build()
    app.add_handler(CommandHandler('start',start)); app.add_handler(CommandHandler('help',help_cmd))
    app.add_handler(CallbackQueryHandler(home_cb,pattern='^home$')); app.add_handler(CallbackQueryHandler(check_sub,pattern='^checksub$')); app.add_handler(CallbackQueryHandler(files_cb,pattern='^files$')); app.add_handler(CallbackQueryHandler(help_cb,pattern='^help$')); app.add_handler(CallbackQueryHandler(myfiles,pattern='^myfiles$')); app.add_handler(CallbackQueryHandler(archive_view,pattern='^archive:')); app.add_handler(CallbackQueryHandler(browse,pattern='^browse:')); app.add_handler(CallbackQueryHandler(file_view,pattern='^file:')); app.add_handler(CallbackQueryHandler(send_file,pattern='^sendfile:')); app.add_handler(CallbackQueryHandler(delete_file,pattern='^delfile:')); app.add_handler(CallbackQueryHandler(extract_all,pattern='^extractall:')); app.add_handler(CallbackQueryHandler(delete_archive,pattern='^delarchive:')); app.add_handler(CallbackQueryHandler(search_start,pattern='^search:')); app.add_handler(CallbackQueryHandler(cleanup,pattern='^cleanup$')); app.add_handler(CallbackQueryHandler(media_prompt,pattern='^(video|audio)$')); app.add_handler(CallbackQueryHandler(admin_cb,pattern='^(admin|adm:)')); app.add_handler(CallbackQueryHandler(channel_cb,pattern='^channel:'))
    app.add_handler(MessageHandler(filters.Document.ALL,media_or_archive)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_input))
    return app

if __name__=='__main__': build_app().run_polling(allowed_updates=Update.ALL_TYPES)
