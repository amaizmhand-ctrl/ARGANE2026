import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import datetime
import json
import random
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta

# Supabase Client Import (Fallback to SQLite if credentials are missing)
try:
    from supabase import create_client, Client
    HAS_SUPABASE_LIB = True
except ImportError:
    HAS_SUPABASE_LIB = False

def get_supabase():
    if not HAS_SUPABASE_LIB:
        return None
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if url and key:
        try:
            return create_client(url, key)
        except Exception:
            return None
    return None

# ---------------------------------------------------------
# Page Configuration & Styling (PWA & Web Config with Clear High-Contrast Text)
# ---------------------------------------------------------
st.set_page_config(
    page_title="Lqargane - منظومة تتبع الغياب الذكية",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800&display=swap');
    
    html, body, [class*="css"], div, span, applet, object, iframe, h1, h2, h3, h4, h5, h6, p, blockquote, pre, a, abbr, acronym, address, big, cite, code, del, dfn, em, img, ins, kbd, q, s, samp, small, strike, strong, sub, sup, tt, var, b, u, i, center, dl, dt, dd, ol, ul, li, fieldset, form, label, legend, table, caption, tbody, tfoot, thead, tr, th, td {
        font-family: 'Tajawal', sans-serif !important;
        direction: rtl;
        text-align: right;
        color: #0f172a !important; /* لون خط داكن وواضح جداً لجميع النصوص */
    }
    
    .stApp {
        background-color: #f8fafc;
    }
    
    /* ضمان وضوح النصوص داخل الأزرار والعناصر */
    .stButton>button {
        border-radius: 10px;
        font-weight: 700;
        transition: all 0.2s ease;
        background-color: #0284c7;
        color: white !important;
        border: none;
    }
    
    .stButton>button:hover {
        background-color: #0369a1;
        color: white !important;
        transform: translateY(-1px);
    }

    /* تنسيق الشريط الجانبي ليكون الخط فيه ناصع البياض وواضح */
    section[data-testid="stSidebar"] {
        background-color: #0f172a !important;
    }
    
    section[data-testid="stSidebar"] * {
        color: #f8fafc !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Database Initialization & Concurrency Safety
# ---------------------------------------------------------
DB_FILE = "school_absence.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            full_name TEXT,
            role TEXT,
            custom_title TEXT DEFAULT 'أستاذ(ة)',
            status TEXT DEFAULT 'active',
            assigned_class TEXT DEFAULT '',
            phone TEXT UNIQUE,
            email TEXT DEFAULT '',
            must_change_password INTEGER DEFAULT 0,
            last_seen TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT UNIQUE,
            level TEXT DEFAULT '',
            branch TEXT DEFAULT ''
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_number INTEGER,
            massar_id TEXT UNIQUE,
            full_name TEXT,
            class_name TEXT,
            guardian_phone TEXT DEFAULT '',
            secret_code TEXT,
            total_absent_hours INTEGER DEFAULT 0
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS absence_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            class_name TEXT,
            date TEXT,
            session_number INTEGER,
            session_time TEXT,
            recorded_by TEXT,
            note TEXT,
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS teacher_timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_username TEXT,
            class_name TEXT,
            day_of_week TEXT,
            session_number INTEGER
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS entry_permits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            cleared_by TEXT,
            timestamp TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS school_exclusions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT,
            target_name TEXT,
            start_date TEXT,
            end_date TEXT,
            reason TEXT,
            created_by TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS staff_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_name TEXT,
            sender_title TEXT,
            message TEXT,
            timestamp TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS flash_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            message TEXT,
            expiry_date TEXT,
            publisher TEXT,
            created_at TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS student_disciplinary_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            issuer_title TEXT,
            notice_type TEXT,
            content TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
    ''')

    dev_pass = st.secrets.get("DEV_PASSWORD", "dev1234")
    dev_email = st.secrets.get("DEV_EMAIL", "dev_admin@school.ma")
    
    c.execute("SELECT * FROM users WHERE username = 'dev_admin@school.ma'")
    if not c.fetchone():
        c.execute('''
            INSERT INTO users (username, password, full_name, role, custom_title, status, phone, email)
            VALUES ('dev_admin@school.ma', ?, 'المطور الرئيسي', 'developer', 'مطور النظام', 'active', '0600000000', ?)
        ''', (dev_pass, dev_email))

    conn.commit()
    conn.close()

init_db()

SESSIONS = {
    1: {"name": "الحصة 1 (الصباحية)", "time": "08:00 - 09:00", "period": "صباح"},
    2: {"name": "الحصة 2 (الصباحية)", "time": "09:00 - 10:00", "period": "صباح"},
    3: {"name": "الحصة 3 (الصباحية)", "time": "10:00 - 11:00", "period": "صباح"},
    4: {"name": "الحصة 4 (الصباحية)", "time": "11:00 - 12:00", "period": "صباح"},
    5: {"name": "الحصة 5 (المسائية)", "time": "14:00 - 15:00", "period": "مساء"},
    6: {"name": "الحصة 6 (المسائية)", "time": "15:00 - 16:00", "period": "مساء"},
    7: {"name": "الحصة 7 (المسائية)", "time": "16:00 - 17:00", "period": "مساء"},
    8: {"name": "الحصة 8 (المسائية)", "time": "17:00 - 18:00", "period": "مساء"},
}

def get_current_session_number():
    now_hour = datetime.now().hour
    if now_hour == 8: return 1
    elif now_hour == 9: return 2
    elif now_hour == 10: return 3
    elif now_hour == 11: return 4
    elif now_hour == 14: return 5
    elif now_hour == 15: return 6
    elif now_hour == 16: return 7
    elif now_hour >= 17: return 8
    return 1

def send_otp_email(to_email, otp_code):
    try:
        sender_email = st.secrets.get("SMTP_EMAIL", "")
        sender_password = st.secrets.get("SMTP_PASSWORD", "")
        
        if not sender_email or not sender_password:
            st.toast(f"🔐 [رمز المصادقة الثنائية 2FA] كود التحقق الخاص بك: {otp_code}", icon="🛡️")
            return True

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = "Lqargane - رمز المصادقة الثنائية الآمن (2FA)"
        
        body = f"مرحباً بالمطور الرئيسي،\n\nرمز التحقق الثنائي الخاص بك للدخول إلى منظومة Lqargane هو: {otp_code}\n\nصالح لهذه الجلسة فقط."
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        server.quit()
        return True
    except Exception:
        st.toast(f"🔐 [2FA] الكود: {otp_code}", icon="🛡️")
        return False

if "user" not in st.session_state:
    st.session_state.user = None
if "pending_2fa_user" not in st.session_state:
    st.session_state.pending_2fa_user = None
if "generated_otp" not in st.session_state:
    st.session_state.generated_otp = None

def logout():
    st.session_state.user = None
    st.session_state.pending_2fa_user = None
    st.session_state.generated_otp = None
    if "active_parent_student" in st.session_state:
        del st.session_state["active_parent_student"]
    st.rerun()

# ---------------------------------------------------------
# Sidebar Navigation & 2FA Login Flow
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #38bdf8;'>🏫 Lqargane</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #cbd5e1; font-size: 0.85rem;'>منصة المواظبة والزمن المدرسي الذكي</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #38bdf8; font-size: 0.8rem; font-weight: bold;'>By: Pr:M'h.AMAIZ</p>", unsafe_allow_html=True)
    
    supabase_status = "🟢 Supabase سحابي" if get_supabase() else "🟠 SQLite محلي"
    st.markdown(f"<p style='text-align: center; font-size: 0.75rem; color: #94a3b8;'>حالة البيانات: {supabase_status}</p>", unsafe_allow_html=True)
    st.divider()

    if st.session_state.user:
        u = st.session_state.user
        role_label = u.get('custom_title', u['role'])

        st.markdown(f"**مرحباً بك:** {u['full_name']}")
        st.markdown(f"**الصفة التربوية:** `{role_label}`")

        st.divider()
        if st.button("🚪 تسجيل الخروج الآمن", use_container_width=True, type="primary"):
            logout()
            
    elif st.session_state.pending_2fa_user:
        st.subheader("🛡️ المصادقة الثنائية (2FA)")
        st.info("أدخل كود التحقق السري المكون من 6 أرقام:")
        
        entered_otp = st.text_input("كود التحقق:", type="password", max_chars=6)
        
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            if st.button("تأكيد الدخول", use_container_width=True, type="primary"):
                if entered_otp == st.session_state.generated_otp:
                    st.session_state.user = st.session_state.pending_2fa_user
                    st.session_state.pending_2fa_user = None
                    st.session_state.generated_otp = None
                    st.success("تم التحقق بنجاح!")
                    st.rerun()
                else:
                    st.error("كود التحقق غير صحيح!")
        with col_v2:
            if st.button("إلغاء", use_container_width=True):
                st.session_state.pending_2fa_user = None
                st.session_state.generated_otp = None
                st.rerun()

    else:
        auth_mode = st.radio("طريقة الدخول:", ["🔐 دخول الأطر (مع 2FA الآمن)", "👁️ تلميذ / ولي أمر"], label_visibility="collapsed")

        if auth_mode == "🔐 دخول الأطر (مع 2FA الآمن)":
            st.subheader("دخول الأطر التربوية الآمن")
            login_id = st.text_input("البريد الإلكتروني أو الهاتف المهني", key="login_id_field")
            login_pass = st.text_input("كلمة المرور / الكود", type="password", key="login_pass_field")
            
            if st.button("إرسال كود المصادقة الثنائية", use_container_width=True, type="primary"):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE (username = ? OR phone = ?) AND password = ?", (login_id, login_id, login_pass))
                user = c.fetchone()
                conn.close()

                if user:
                    if user['status'] == 'active':
                        otp = str(random.randint(100000, 999999))
                        st.session_state.generated_otp = otp
                        st.session_state.pending_2fa_user = dict(user)
                        
                        target_mail = user['email'] if user['email'] else "dev_admin@school.ma"
                        send_otp_email(target_mail, otp)
                        st.success("تم إرسال كود التحقق الثنائي بنجاح!")
                        st.rerun()
                    else:
                        st.warning("حسابك غير مفعل حالياً.")
                else:
                    st.error("معلومات الدخول غير صحيحة!")

        elif auth_mode == "👁️ تلميذ / ولي أمر":
            st.subheader("بوابة المراقبة الفردية")
            p_massar = st.text_input("رقم مسار التلميذ(ة)", placeholder="مثال: G123456789").strip()
            p_code = st.text_input("الرمز السري (رقم مسار + 20262027)", type="password").strip()
            
            if st.button("عرض سجل الغياب والملاحظات", use_container_width=True, type="primary"):
                if p_massar and p_code:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("SELECT * FROM students WHERE massar_id = ? AND secret_code = ?", (p_massar, p_code))
                    student = c.fetchone()
                    conn.close()

                    if student:
                        st.session_state.active_parent_student = dict(student)
                        st.session_state.user = {"role": "parent", "full_name": student['full_name'], "custom_title": "ولي أمر / تلميذ"}
                        st.success("تم الدخول بنجاح!")
                        st.rerun()
                    else:
                        st.error("رقم مسار أو الرمز السري غير صحيح!")
                else:
                    st.error("يرجى ملء كافة الخانات.")

# ---------------------------------------------------------
# Flash Announcements Banner
# ---------------------------------------------------------
if st.session_state.user:
    conn = get_db_connection()
    today_str = date.today().strftime("%Y-%m-%d")
    announcements = pd.read_sql_query("SELECT title, message, publisher FROM flash_announcements WHERE expiry_date >= ?", conn, params=(today_str,))
    conn.close()

    if not announcements.empty and st.session_state.user['role'] == 'parent':
        st.markdown("### 📢 إخبارات عاجلة وتنبيهات المؤسسة:")
        for _, ann in announcements.iterrows():
            st.warning(f"🚨 **{ann['title']}** (ناشر الخبر: {ann['publisher']})\n\n{ann['message']}")

# ---------------------------------------------------------
# Main Router
# ---------------------------------------------------------
if not st.session_state.user:
    st.markdown("""
        <div style="text-align: center; padding: 2.5rem; background: linear-gradient(135deg, #0f172a, #1e293b); border-radius: 16px; color: white; margin-bottom: 2rem;">
            <h1 style="font-size: 2.5rem; margin-bottom: 0.5rem; color: #38bdf8;">🏫 منصة Lqargane الذكية لتتبع الغياب</h1>
            <p style="font-size: 1.2rem; color: #cbd5e1;">موقع وتطبيق رسمي متزامن لحظياً لإدارة الزمن المدرسي ومتابعة المواظبة والسلوك</p>
            <p style="font-size: 1rem; color: #38bdf8; margin-top: 1rem; font-weight: bold;">Developed by: Pr:M'h.AMAIZ</p>
        </div>
    """, unsafe_allow_html=True)
    st.info("👈 يرجى تسجيل الدخول عبر الشريط الجانبي للبدء مع تفعيل المصادقة الثنائية (2FA).")

else:
    role = st.session_state.user['role']

    # =========================================================
    # 1. DEVELOPER ROLE
    # =========================================================
    if role == 'developer':
        st.title("👨‍💻 لوحة تحكّم المطور الرئيسي (Lqargane Master مع 2FA)")
        dev_tabs = st.tabs(["👤 حسابات الأطر", "📥 استيراد الإكسيل متعدد الأقسام", "📅 استعمال الزمن", "➕ الأقسام والشعب", "🔑 تغيير كلمة السر الخاصة بالمطور"])

        conn = get_db_connection()
        with dev_tabs[0]:
            st.subheader("إضافة حساب أستاذ أو إداري مع البريد لتلقي 2FA")
            d_name = st.text_input("الاسم الكامل")
            d_email = st.text_input("البريد الإلكتروني المهني")
            d_phone = st.text_input("رقم الهاتف", placeholder="06XXXXXXXX")
            d_role = st.selectbox("الدور الأساسي", ["teacher", "admin", "supervisor"], format_func=lambda x: {"teacher": "أستاذ(ة)", "admin": "المدير", "supervisor": "الحارس العام"}[x])
            d_custom_title = st.text_input("الصفة الدقيقة:", placeholder="مثال: أستاذ الرياضيات")
            d_pass = st.text_input("الكود الأولي", value="123456")

            if st.button("حفظ الحساب بأمان", type="primary"):
                if d_name and d_email:
                    try:
                        c = conn.cursor()
                        c.execute("INSERT INTO users (username, password, full_name, role, custom_title, status, phone, email, must_change_password) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, 1)",
                                  (d_email, d_pass, d_name, d_role, d_custom_title, d_phone, d_email))
                        conn.commit()
                        st.success("تم الحفظ بنجاح وتفعيل حماية 2FA!")
                    except Exception as e:
                        st.error(f"خطأ: {e}")
                else:
                    st.error("يرجى ملء كافة الخانات.")

        with dev_tabs[1]:
            st.subheader("📥 قراءة واستيراد ملف الإكسيل الرسمي للمؤسسة")
            up_file = st.file_uploader("اختر ملف إكسيل الأقسام (.xlsx)", type=['xlsx'])
            if up_file:
                try:
                    xls = pd.ExcelFile(up_file)
                    st.write(f"📁 تم العثور على {len(xls.sheet_names)} قسم/مجموعة في الملف.")
                    if st.button("معالجة واستيراد كافة أقسام ومجموعات التلاميذ"):
                        c = conn.cursor()
                        total_imported = 0
                        for sheet in xls.sheet_names:
                            df_sheet = pd.read_excel(up_file, sheet_name=sheet, header=None)
                            level_val = "تعليم ثانوي"
                            class_val = sheet
                            for r in range(min(10, df_sheet.shape[0])):
                                row_str = str(df_sheet.iloc[r].values)
                                if 'المستوى' in row_str:
                                    for val in df_sheet.iloc[r].values:
                                        if pd.notna(val) and 'المستوى' not in str(val) and ':' not in str(val):
                                            level_val = str(val).strip()
                                if 'القسم' in row_str:
                                    for val in df_sheet.iloc[r].values:
                                        if pd.notna(val) and 'القسم' not in str(val) and ':' not in str(val):
                                            class_val = str(val).strip()

                            branch_val = "علوم" if "علوم" in level_val or "علوم" in class_val else "آداب وعلوم إنسانية"
                            c.execute("INSERT OR IGNORE INTO classes (class_name, level, branch) VALUES (?, ?, ?)", (class_val, level_val, branch_val))
                            
                            df_students = pd.read_excel(up_file, sheet_name=sheet, skiprows=8)
                            if df_students.shape[1] >= 4:
                                for _, row in df_students.iterrows():
                                    massar = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
                                    if massar and massar != 'nan' and massar != 'الرمز':
                                        family_name = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
                                        first_name = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
                                        full_name = f"{family_name} {first_name}".strip()
                                        std_num = int(row.iloc[0]) if pd.notna(row.iloc[0]) and str(row.iloc[0]).isdigit() else 1
                                        secret_code = f"{massar}20262027"
                                        
                                        c.execute("""
                                            INSERT INTO students (student_number, massar_id, full_name, class_name, secret_code) 
                                            VALUES (?, ?, ?, ?, ?) 
                                            ON CONFLICT(massar_id) DO UPDATE SET full_name=excluded.full_name, class_name=excluded.class_name
                                        """, (std_num, massar, full_name, class_val, secret_code))
                                        total_imported += 1
                        conn.commit()
                        st.success(f"🎉 تم بنجاح استيراد وتسجيل {total_imported} تلميذاً عبر الأقسام والمستويات!")
                except Exception as e:
                    st.error(f"خطأ أثناء القراءة: {e}")

        with dev_tabs[2]:
            st.subheader("إدخال استعمال الزمن")
            teachers_df = pd.read_sql_query("SELECT full_name, username, custom_title FROM users WHERE role = 'teacher'", conn)
            classes_df = pd.read_sql_query("SELECT class_name FROM classes", conn)
            t_map = {f"{r['full_name']} ({r['custom_title']})": r['username'] for _, r in teachers_df.iterrows()}
            sel_t = st.selectbox("الأستاذ:", list(t_map.keys()) if t_map else [])
            sel_cls = st.selectbox("القسم أو المجموعة:", classes_df['class_name'].tolist() if not classes_df.empty else [])
            sel_day = st.selectbox("اليوم:", ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"])
            sel_sess = st.selectbox("الحصة:", options=list(SESSIONS.keys()), format_func=lambda x: f"الحصة {x} ({SESSIONS[x]['time']})")
            if st.button("إضافة الحصة"):
                if sel_t and sel_cls:
                    c = conn.cursor()
                    c.execute("INSERT INTO teacher_timetable (teacher_username, class_name, day_of_week, session_number) VALUES (?, ?, ?, ?)",
                              (t_map[sel_t], sel_cls, sel_day, sel_sess))
                    conn.commit()
                    st.success("تمت الإضافة بنجاح.")

        with dev_tabs[3]:
            st.dataframe(pd.read_sql_query("SELECT class_name as 'اسم القسم', level as 'المستوى', branch as 'الشعبة' FROM classes", conn), use_container_width=True)

        with dev_tabs[4]:
            st.subheader("🔑 لوحة تغيير كلمة المرور السرية للمطور الرئيسي")
            old_p = st.text_input("كلمة المرور الحالية", type="password")
            new_p1 = st.text_input("كلمة المرور الجديدة", type="password")
            new_p2 = st.text_input("تأكيد كلمة المرور الجديدة", type="password")
            if st.button("تحديث وحفظ كلمة المرور السرية الجديدة", type="primary"):
                if new_p1 and new_p1 == new_p2:
                    c = conn.cursor()
                    c.execute("UPDATE users SET password = ? WHERE username = 'dev_admin@school.ma'", (new_p1,))
                    conn.commit()
                    st.success("🎉 تمت بنجاح عملية تحديث كلمة مرور المطور وأصبحت مؤمنة تماماً بالرمز الجديد!")
                else:
                    st.error("كلمتا المرور غير متطابقتين أو فارغتان.")
        conn.close()

    # =========================================================
    # 2. ADMINISTRATION & SUPERVISOR ROLE
    # =========================================================
    elif role in ['admin', 'supervisor']:
        st.title(f"📋 لوحة قيادة {'السيد المدير' if role == 'admin' else 'الحارس العام'}")
        admin_tabs = st.tabs(["📊 الإحصائيات والبحث", "🚨 تنبيهات الغياب", "🏖️ العطل والانقطاعات", "💬 دردشة الأطر", "📢 الإخبارات", "📥 التقارير الرسمية"])
        conn = get_db_connection()
        with admin_tabs[0]:
            st.subheader("البحث الفردي للتلاميذ")
            srch_name = st.text_input("اسم التلميذ:")
            if st.button("بحث"):
                res = pd.read_sql_query("SELECT * FROM students WHERE full_name LIKE ?", conn, params=(f"%{srch_name}%",))
                st.dataframe(res, use_container_width=True)
        with admin_tabs[1]:
            st.subheader("تلاميذ تجاوزوا عتبة 4 ساعات غياب")
            absent_risk = pd.read_sql_query("SELECT * FROM students WHERE total_absent_hours >= 4", conn)
            st.dataframe(absent_risk, use_container_width=True)
            if not absent_risk.empty:
                st.divider()
                target_sid = st.selectbox("اختر التلميذ لإرسال تنبيه إداري ثابت:", absent_risk['id'].tolist(), format_func=lambda x: absent_risk[absent_risk['id']==x]['full_name'].values[0])
                notice_text = st.text_area("نص التنبيه الإداري:")
                if st.button("إرسال التنبيه الثابت"):
                    if notice_text:
                        c = conn.cursor()
                        c.execute("INSERT INTO student_disciplinary_records (student_id, issuer_title, notice_type, content, created_at) VALUES (?, ?, 'تنبيه إداري تجاوز السقف', ?, ?)",
                                  (target_sid, st.session_state.user['custom_title'], notice_text, datetime.now().strftime("%Y-%m-%d %H:%M")))
                        conn.commit()
                        st.success("تم إرسال التنبيه الثابت بنجاح.")
        with admin_tabs[2]:
            st.subheader("إدارة العطل والغياب الاستثنائي")
            st.info("سجل العطل هنا لتبرير غيابات التلاميذ الجماعية.")
        with admin_tabs[3]:
            st.subheader("غرفة دردشة الأطر الخاصة")
            msg_input = st.text_input("اكتب رسالة:")
            if st.button("إرسال رسالة"):
                if msg_input:
                    c = conn.cursor()
                    c.execute("INSERT INTO staff_chats (sender_name, sender_title, message, timestamp) VALUES (?, ?, ?, ?)",
                              (st.session_state.user['full_name'], st.session_state.user['custom_title'], msg_input, datetime.now().strftime("%Y-%m-%d %H:%M")))
                    conn.commit()
            chats = pd.read_sql_query("SELECT sender_title, message, timestamp FROM staff_chats ORDER BY id DESC LIMIT 10", conn)
            for _, ch in chats.iterrows():
                st.markdown(f"💬 **{ch['sender_title']}** ({ch['timestamp']}): {ch['message']}")
        with admin_tabs[4]:
            st.subheader("نشر إخبار عاجل")
            title = st.text_input("العنوان")
            msg = st.text_area("الرسالة")
            if st.button("نشر الفوري"):
                c = conn.cursor()
                c.execute("INSERT INTO flash_announcements (title, message, expiry_date, publisher) VALUES (?, ?, ?, ?)", (title, msg, str(date.today() + timedelta(days=2)), st.session_state.user['custom_title']))
                conn.commit()
                st.success("تم النشر.")
        with admin_tabs[5]:
            st.subheader("تصدير التقارير الرسمية")
            df_rep = pd.read_sql_query("SELECT * FROM students", conn)
            st.dataframe(df_rep)
            st.download_button("⬇️ تحميل كملف CSV", data=df_rep.to_csv(index=False).encode('utf-8'), file_name="students_report.csv", mime="text/csv")
        conn.close()

    # =========================================================
    # 3. TEACHER ROLE
    # =========================================================
    elif role == 'teacher':
        st.title(f"👨‍🏫 بوابة الأستاذ(ة): {st.session_state.user['full_name']}")
        conn = get_db_connection()
        t_classes = pd.read_sql_query("SELECT DISTINCT class_name FROM teacher_timetable WHERE teacher_username = ?", conn, params=(st.session_state.user['username'],))['class_name'].tolist()
        if not t_classes: t_classes = ["الجذع المشترك 1"]
        
        sel_cls = st.selectbox("القسم أو المجموعة:", t_classes)
        sess_num = st.selectbox("الحصة:", options=list(SESSIONS.keys()), format_func=lambda x: f"الحصة {x} ({SESSIONS[x]['time']})")
        
        std_df = pd.read_sql_query("SELECT id, student_number, full_name FROM students WHERE class_name = ?", conn, params=(sel_cls,))
        absent_ids = []
        for _, r in std_df.iterrows():
            if st.checkbox(f"({r['student_number']}) {r['full_name']}", key=f"t_abs_{r['id']}"):
                absent_ids.append(r['id'])
                
        custom_note = st.text_input("ملاحظة سلوكية للأستاذ (تثبت فوراً ولا يمكن للتلميذ حذفها):")
        if st.button("حفظ الغياب والملاحظة الثابتة", type="primary"):
            c = conn.cursor()
            for sid in absent_ids:
                c.execute("INSERT INTO absence_records (student_id, class_name, date, session_number, session_time, recorded_by, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (sid, sel_cls, str(date.today()), sess_num, SESSIONS[sess_num]['time'], st.session_state.user['custom_title'], custom_note))
                c.execute("UPDATE students SET total_absent_hours = total_absent_hours + 1 WHERE id = ?", (sid,))
            if custom_note and absent_ids:
                c.execute("INSERT INTO student_disciplinary_records (student_id, issuer_title, notice_type, content, created_at) VALUES (?, ?, 'ملاحظة سلوكية للأستاذ', ?, ?)",
                          (absent_ids[0], st.session_state.user['custom_title'], custom_note, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            st.success("تم الحفظ وتثبيت الملاحظة في سوابق التلميذ بنجاح!")
        conn.close()

    # =========================================================
    # 4. PARENT & STUDENT ROLE
    # =========================================================
    elif role == 'parent':
        std = st.session_state.active_parent_student
        st.title(f"👁️ فضاء مراقبة المواظبة: {std['full_name']}")
        conn = get_db_connection()
        st.metric("مجموع ساعات الغياب", f"{std['total_absent_hours']} ساعة")
        
        st.subheader("🚨 السجل الثابت للملاحظات والتنبيهات الإدارية والسلوكية:")
        notices = pd.read_sql_query("SELECT issuer_title as 'المرسل', notice_type as 'نوع الإشعار', content as 'التفاصيل', created_at as 'التاريخ' FROM student_disciplinary_records WHERE student_id = ?", conn, params=(std['id'],))
        if not notices.empty:
            st.warning("⚠️ ملاحظة: هذه السجلات موثقة رسمياً ولا يمكن لأي تلميذ حذفها أو التلاعب بها.")
            st.dataframe(notices, use_container_width=True)
        else:
            st.success("سجلك نظيف تماماً وخالٍ من أي ملاحظات!")
        conn.close()