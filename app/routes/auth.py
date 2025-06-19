from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from config import DB_CONFIG
from app.models import Base, Users 
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tạo engine và session cho SQLAlchemy
engine = create_engine(f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")
Base.metadata.create_all(engine)  

auth_bp = Blueprint('auth', __name__)



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
            with Session(engine) as db_session:
                # Kiểm tra trùng username hoặc email
                existing_user = db_session.query(Users).filter(
                    (Users.username == username) | (Users.email == email)
                ).first()
                
                if existing_user:
                    if existing_user.username == username:
                        flash("Tên đăng nhập đã tồn tại", "error")
                    else:
                        flash("Email đã được đăng ký", "error")
                    return redirect(url_for('auth.register'))

                # Hash password và tạo user mới
                hashed_password = generate_password_hash(password)
                new_user = Users(
                    fullname=fullname,
                    username=username,
                    age=age,
                    email=email,
                    password=hashed_password
                )
                db_session.add(new_user)
                db_session.commit()
                
                logger.info(f"User registered: {username}")
                flash("Đăng ký thành công! Vui lòng đăng nhập", "success")
                return redirect(url_for('auth.login')) 

        except Exception as err:
            logger.error(f"Database error: {err}")
            flash("Lỗi hệ thống, vui lòng thử lại sau", "error")
            return redirect(url_for('auth.register'))

    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():  
    if request.method == 'POST':
        # Validate dữ liệu đầu vào
        email = request.form['email'].strip().lower()
        password = request.form['password']

        # Xử lý đăng nhập
        try:
            with Session(engine) as db_session:
                # Kiểm tra email có tồn tại không
                user = db_session.query(Users).filter(Users.email == email).first()
                
                if not user:
                    flash("Email không tồn tại trong hệ thống", "error")
                    return redirect(url_for('auth.login'))
                
                # Kiểm tra mật khẩu 
                if not check_password_hash(user.password, password):
                    flash("Mật khẩu không chính xác", "error")
                    return redirect(url_for('auth.login'))
                
                # Đăng nhập thành công - lưu thông tin vào session
                session['user_id'] = user.user_id
                session['username'] = user.username 
                session['email'] = user.email
                session['role'] = user.role

                # Phân hướng theo role
                if user.role == 'admin':
                    flash("Đăng nhập thành công!", "success")
                    return redirect(url_for('admin.dashboard'))
                else:
                    flash("Đăng nhập thành công!", "success")
                    return redirect(url_for('user.home'))

        except Exception as err:
            logger.error(f"Database error: {err}")
            flash("Lỗi hệ thống, vui lòng thử lại sau", "error")
            return redirect(url_for('auth.login'))

    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():  
    session.clear()
    flash('Đã đăng xuất thành công', 'success')
    return render_template('user/index.html')