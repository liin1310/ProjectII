from flask import Blueprint, render_template, request, redirect, url_for, flash,session
import mysql.connector
import logging
from werkzeug.security import generate_password_hash, check_password_hash
from config import DB_CONFIG

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)
@auth_bp.route('/')
def index():
    if 'username' in session:
        return render_template('user/index.html', username=session['username'])
    return render_template('user/index.html')
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Validate dữ liệu đầu vào
        try:
            fullname = request.form['fullname'].strip()
            username = request.form['username'].strip()
            age = int(request.form['age'])
            email = request.form['email'].strip().lower()
            password = request.form['password']
            
            if age <= 0:
                flash("Tuổi phải là số dương", "error")
                return redirect(url_for('auth.register'))
                
            if len(password) < 6:
                flash("Mật khẩu phải có ít nhất 6 ký tự", "error")
                return redirect(url_for('auth.register'))
                
            if password != request.form['confirm_password']: 
                flash("Mật khẩu xác nhận không khớp", "error")
                return redirect(url_for('auth.register'))
                
        except ValueError:
            flash("Dữ liệu nhập không hợp lệ", "error")
            return redirect(url_for('auth.register'))
        except KeyError as e:
            flash(f"Thiếu thông tin: {e}", "error")
            return redirect(url_for('auth.register'))

        # Xử lý đăng ký
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            if not conn.is_connected():
                raise mysql.connector.Error("Không thể kết nối database")
                
            cursor = conn.cursor(dictionary=True)

            # Kiểm tra trùng
            cursor.execute("SELECT username, email FROM users WHERE username = %s OR email = %s", 
                         (username, email))
            existing = cursor.fetchone()
            
            if existing:
                if existing['username'] == username:
                    flash("Tên đăng nhập đã tồn tại", "error")
                else:
                    flash("Email đã được đăng ký", "error")
                return redirect(url_for('auth.register'))

            # Hash password và tạo user
            hashed_password = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, fullname, age, email, password) VALUES (%s, %s, %s, %s, %s)", 
                (username, fullname, age, email, hashed_password)
            )
            conn.commit()
            
            logger.info(f"User registered: {username}")
            flash("Đăng ký thành công! Vui lòng đăng nhập", "success")
            return redirect(url_for('auth.login')) 

        except mysql.connector.Error as err:
            logger.error(f"Database error: {err}")
            flash("Lỗi hệ thống, vui lòng thử lại sau", "error")
            return redirect(url_for('auth.register'))
            
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():  
    if request.method == 'POST':
        # Validate dữ liệu đầu vào
        email = request.form['email'].strip().lower()
        password = request.form['password']

        # Xử lý đăng nhập
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            if not conn.is_connected():
                raise mysql.connector.Error("Không thể kết nối database")
                
            cursor = conn.cursor(dictionary=True)

            # Kiểm tra email có tồn tại không
            cursor.execute("SELECT user_id, email, password, role FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            if not user:
                flash("Email không tồn tại trong hệ thống", "error")
                return redirect(url_for('auth.login'))
            
            # Kiểm tra mật khẩu 
            if not check_password_hash(user['password'], password):
                flash("Mật khẩu không chính xác", "error")
                return redirect(url_for('auth.login'))
            
            # Đăng nhập thành công - lưu thông tin vào session
            session['user_id'] = user['user_id']
            session['email'] = user['email']
            session['role'] = user['role']

            #Phân hướng theo role
            if user['role'] == 'admin':
                flash("Đăng nhập thành công!", "success")
                return redirect(url_for('admin.dashboard'))  # Chuyển hướng về trang chủ
            else:
                flash("Đăng nhập thành công!", "success")
                return redirect(url_for('auth.index'))  # Chuyển hướng về trang chủ

        except mysql.connector.Error as err:
            logger.error(f"Database error: {err}")
            flash("Lỗi hệ thống, vui lòng thử lại sau", "error")
            return redirect(url_for('auth.login'))
            
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()

    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():  
    session.clear()
    flash('Đã đăng xuất thành công', 'success')
    return redirect(url_for('auth.index'))
