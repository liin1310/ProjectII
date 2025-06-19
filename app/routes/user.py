from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import logging
import secrets
from config import DB_CONFIG
from app.models import Base, Users, Books, Authors, Categories, ReadingHistory, Ratings, t_book_categories
from sqlalchemy import create_engine, or_, func, and_, desc
from sqlalchemy.orm import Session, aliased
from datetime import datetime

user_bp = Blueprint('user', __name__)
RatingsAlias = aliased(Ratings)
# Tạo logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Tạo engine và session cho SQLAlchemy
engine = create_engine(f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")
Base.metadata.create_all(engine)

# Yêu cầu đăng nhập
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') == 'admin':
            flash('Vui lòng đăng nhập.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Kiểm tra CSRF token
def check_csrf_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            token = session.get('csrf_token')
            form_token = request.form.get('csrf_token')
            header_token = request.headers.get('X-CSRFToken')
            if not token or (token != form_token and token != header_token):
                if request.is_json:
                    return jsonify({'success': False, 'error': 'CSRF token không hợp lệ'})
                flash('CSRF token không hợp lệ', 'danger')
                return redirect(request.url)
        return f(*args, **kwargs)
    return decorated_function

# Làm mới CSRF token
def refresh_csrf_token():
    session['csrf_token'] = secrets.token_hex(16)

# Tạo CSRF token
@user_bp.before_request
def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)

@user_bp.route('/')
@login_required
def home():

    try:
        with Session(engine) as db_session:
            # Sách có điểm đánh giá trung bình cao nhất
            featured_books_query = (
                db_session.query(
                    Books.book_id,
                    Books.title,
                    Books.cover_url,
                    Authors.name.label("author_name"),
                    func.avg(Ratings.rating).label("avg_rating")
                )
                .join(Ratings, Ratings.book_id == Books.book_id)
                .outerjoin(Authors, Books.author_id == Authors.author_id)
                .group_by(Books.book_id)
                .order_by(func.avg(Ratings.rating).desc())
                .limit(4)
                .all()
            )

            featured_books = [
                {
                    "book_id": book.book_id,
                    "title": book.title,
                    "cover_url": book.cover_url,
                    "author_name": book.author_name,
                    "avg_rating": round(book.avg_rating, 1) if book.avg_rating else None
                }
                for book in featured_books_query
            ]

            # Sách mới cập nhật
            latest_books_query = (
                db_session.query(
                    Books.book_id,
                    Books.title,
                    Books.cover_url,
                    Books.published_year,
                    func.group_concat(Categories.name).label("category_name")
                )
                .outerjoin(t_book_categories, Books.book_id == t_book_categories.c.book_id)
                .outerjoin(Categories, t_book_categories.c.category_id == Categories.category_id)
                .group_by(Books.book_id)
                .order_by(Books.created_at.desc())
                .limit(4)
                .all()
            )

            books = [
                {
                    "book_id": b.book_id,
                    "title": b.title,
                    "cover_url": b.cover_url,
                    "published_year": b.published_year,
                    "category_name": b.category_name
                }
                for b in latest_books_query
            ]

            # Sách có lượt đọc nhiều nhất
            most_read_books_query = (
                db_session.query(
                    Books.book_id,
                    Books.title,
                    Books.cover_url,
                    Authors.name.label("author_name"),
                    func.count(ReadingHistory.user_id).label("read_count")
                )
                .join(ReadingHistory, ReadingHistory.book_id == Books.book_id)
                .outerjoin(Authors, Books.author_id == Authors.author_id)
                .group_by(Books.book_id)
                .order_by(func.count(ReadingHistory.user_id).desc())
                .limit(4)
                .all()
            )

            most_read_books = [
                {
                    "book_id": book.book_id,
                    "title": book.title,
                    "cover_url": book.cover_url,
                    "author_name": book.author_name,
                    "read_count": book.read_count
                }
                for book in most_read_books_query
            ]
            return render_template(
                "user/index.html",
                featured_books=featured_books,
                books=books,
                most_read_books=most_read_books
            )

    except Exception as e:
        logger.error(f"Lỗi khi hiển thị trang chủ: {str(e)}", exc_info=True)
        flash("Không thể tải trang chủ", "danger")
        return redirect(url_for('user.home'))


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# ////////////////////////////////       Quản lý tài khoản          ///////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# Xem thông tin
@user_bp.route('/profile')
@login_required
def profile():
    try:
        with Session(engine) as db_session:
            user = db_session.query(Users).filter(Users.user_id == session['user_id']).first()
            if not user:
                flash('Không tìm thấy thông tin người dùng', 'danger')
                return redirect(url_for('auth.login'))
            return render_template('user/profile/profile.html', user=user, csrf_token=session.get('csrf_token'))
    except Exception as e:
        logger.error(f"Profile error: {str(e)}", exc_info=True)
        flash('Lỗi khi tải thông tin người dùng', 'danger')
        return redirect(url_for('auth.login'))

# Cập nhật thông tin
@user_bp.route('/updateProfile', methods=['GET', 'POST'])
@login_required
@check_csrf_token
def updateProfile():
    try:
        with Session(engine) as db_session:
            user = db_session.query(Users).filter(Users.user_id == session['user_id']).first()
            if not user:
                flash('Không tìm thấy thông tin người dùng', 'danger')
                return redirect(url_for('auth.login'))

            if request.method == 'POST':
                fullname = request.form.get('fullname', '').strip()
                username = request.form.get('username', '').strip()
                email = request.form.get('email', '').strip().lower()
                age_str = request.form.get('age', '').strip()

                # Kiểm tra dữ liệu đầu vào
                if not all([fullname, username, email]):
                    flash('Vui lòng điền đầy đủ các trường bắt buộc', 'danger')
                    user_dict = {'fullname': fullname, 'username': username, 'email': email, 'age': age_str}
                    return render_template('user/profile/updateProfile.html', user=user_dict, csrf_token=session.get('csrf_token'))

                # Kiểm tra và chuyển đổi tuổi
                try:
                    age = int(age_str) if age_str else None
                    if age is not None and (age < 0 or age > 150):
                        raise ValueError('Tuổi không hợp lệ')
                except ValueError:
                    flash('Tuổi phải là một số hợp lệ', 'danger')
                    user_dict = {'fullname': fullname, 'username': username, 'email': email, 'age': age_str}
                    return render_template('user/profile/updateProfile.html', user=user_dict, csrf_token=session.get('csrf_token'))

                # Kiểm tra email trùng
                existing_user = db_session.query(Users).filter(
                    Users.email == email,
                    Users.user_id != session['user_id']
                ).first()
                if existing_user:
                    flash('Email đã được sử dụng bởi tài khoản khác!', 'danger')
                    user_dict = {'fullname': fullname, 'username': username, 'email': email, 'age': age}
                    return render_template('user/profile/updateProfile.html', user=user_dict, csrf_token=session.get('csrf_token'))

                # Kiểm tra xem trùng username không
                existing_username = db_session.query(Users).filter(
                    Users.username == username,
                    Users.user_id != session['user_id']
                ).first()
                if existing_username:
                    flash('Username đã được sử dụng bởi tài khoản khác!', 'danger')
                    user_dict = {'fullname': fullname, 'username': username, 'email': email, 'age': age}
                    return render_template('user/profile/updateProfile.html', user=user_dict, csrf_token=session.get('csrf_token'))
                # Cập nhật thông tin
                user.fullname = fullname
                user.username = username
                user.email = email
                user.age = age
                db_session.commit()

                flash('Cập nhật thông tin thành công!', 'success')
                return redirect(url_for('user.profile'))

            # GET request
            user_dict = {
                'fullname': user.fullname,
                'username': user.username,
                'email': user.email,
                'age': user.age if user.age is not None else ''
            }
            return render_template('user/profile/updateProfile.html', user=user_dict, csrf_token=session.get('csrf_token'))

    except Exception as e:
        logger.error(f"Update profile error: {str(e)}", exc_info=True)
        flash('Lỗi hệ thống, vui lòng thử lại', 'danger')
        user_dict = {
            'fullname': request.form.get('fullname', ''),
            'username': request.form.get('username', ''),
            'email': request.form.get('email', ''),
            'age': request.form.get('age', '')
        }
        return render_template('user/profile/updateProfile.html', user=user_dict, csrf_token=session.get('csrf_token'))

# Thay đổi mật khẩu
@user_bp.route('/changePassword', methods=['GET', 'POST'])
@login_required
@check_csrf_token
def changePassword():
    try:
        with Session(engine) as db_session:
            if request.method == 'POST':
                old_password = request.form.get('old_password', '').strip()
                new_password = request.form.get('new_password', '').strip()
                confirm_password = request.form.get('confirm_password', '').strip()

                # Kiểm tra dữ liệu đầu vào
                if not all([old_password, new_password, confirm_password]):
                    flash('Vui lòng điền đầy đủ các trường', 'danger')
                    return render_template('user/profile/changePassword.html', csrf_token=session.get('csrf_token'))

                # Kiểm tra độ dài mật khẩu
                if len(new_password) < 6:
                    flash('Mật khẩu mới phải dài ít nhất 6 ký tự', 'danger')
                    return render_template('user/profile/changePassword.html', csrf_token=session.get('csrf_token'))

                # Kiểm tra mật khẩu xác nhận
                if new_password != confirm_password:
                    flash('Mật khẩu xác nhận không khớp', 'danger')
                    return render_template('user/profile/changePassword.html', csrf_token=session.get('csrf_token'))

                # Kiểm tra mật khẩu mới trùng mật khẩu cũ
                if new_password == old_password:
                    flash('Mật khẩu mới không được trùng với mật khẩu cũ!', 'danger')
                    return render_template('user/profile/changePassword.html', csrf_token=session.get('csrf_token'))

                user = db_session.query(Users).filter(Users.user_id == session['user_id']).first()
                if not user:
                    flash('Không tìm thấy thông tin người dùng', 'danger')
                    return redirect(url_for('auth.login'))

                # Kiểm tra mật khẩu cũ
                if not check_password_hash(user.password, old_password):
                    flash('Mật khẩu cũ không chính xác', 'danger')
                    return render_template('user/profile/changePassword.html', csrf_token=session.get('csrf_token'))

                # Cập nhật mật khẩu mới
                user.password = generate_password_hash(new_password)
                db_session.commit()

                flash('Cập nhật mật khẩu thành công! Vui lòng đăng nhập lại.', 'success')
                session.clear()
                session['csrf_token'] = secrets.token_hex(16)  # Tạo token mới sau khi xóa session
                return redirect(url_for('auth.login'))

            return render_template('user/profile/changePassword.html', csrf_token=session.get('csrf_token'))

    except Exception as e:
        logger.error(f"Change password error: {e}", exc_info=True)
        flash('Lỗi hệ thống, vui lòng thử lại', 'danger')
        return render_template('user/profile/changePassword.html', csrf_token=session.get('csrf_token'))

@user_bp.app_context_processor
def inject_categories():
    try:
        with Session(engine) as db_session:
            categories = db_session.query(Categories).order_by(Categories.name).all()
            return {'categories': categories}
    except Exception as e:
            logger.error(f"Error loading categories: {str(e)}", exc_info=True)
            return {'categories': []}

# Xem danh sách sách
@user_bp.route('/library')
@login_required
def library():
    try:
        with Session(engine) as db_session:
            # Subquery để lấy lịch sử đọc gần nhất
            subquery = (
                db_session.query(
                    ReadingHistory.book_id,
                    ReadingHistory.user_id,
                    ReadingHistory.last_position,
                    ReadingHistory.last_read_at
                )
                .filter(ReadingHistory.user_id == session['user_id'])
                .filter(
                    ReadingHistory.last_read_at == db_session.query(
                        func.max(ReadingHistory.last_read_at)
                    )
                    .filter(ReadingHistory.user_id == session['user_id'])
                    .correlate(ReadingHistory)
                    .scalar_subquery()
                )
                .subquery()
            )

            # Truy vấn chính
            books_query = (
                db_session.query(
                    Books.book_id,
                    Books.title,
                    Books.cover_url,
                    Authors.name.label('author_name'),
                    func.group_concat(Categories.name).label('category_names'),
                    subquery.c.last_position,
                    subquery.c.last_read_at.label('last_read')
                )
                .outerjoin(Authors, Books.author_id == Authors.author_id)
                .outerjoin(t_book_categories, Books.book_id == t_book_categories.c.book_id)
                .outerjoin(Categories, t_book_categories.c.category_id == Categories.category_id)
                .join(subquery, Books.book_id == subquery.c.book_id)
                .group_by(Books.book_id, Authors.name, subquery.c.last_position, subquery.c.last_read_at)
            )

            books = [
                {
                    'book_id': book_id,
                    'title': title,
                    'cover_url': cover_url,
                    'author_name': author_name,
                    'category_names': category_names.replace(',', ', ') if category_names else '',
                    'last_position': last_position,
                    'last_read': last_read
                }
                for book_id, title, cover_url, author_name, category_names, last_position, last_read in books_query.all()
            ]

            logger.info(f"Rendering library for user_id: {session['user_id']}")
            return render_template('user/books/library.html', books=books, csrf_token=session.get('csrf_token'))

    except Exception as e:
        logger.error(f"Library error: {str(e)}", exc_info=True)
        flash('Lỗi khi tải thư viện sách', 'danger')
        return redirect(url_for('auth.index'))

@user_bp.route('/book/<int:book_id>')
@login_required
def book_detail(book_id):
    try:
        with Session(engine) as db_session:
            # Subquery: Thống kê đánh giá cho mỗi sách
            rating_subq = (
                db_session.query(
                    Ratings.book_id,
                    func.avg(Ratings.rating).label("average_rating"),
                    func.count(Ratings.rating_id).label("rating_count"),
                    func.max(Ratings.created_at).label("last_rating_at")
                )
                .group_by(Ratings.book_id)
                .subquery()
            )

            # Truy vấn chính
            book_query = (
                db_session.query(
                    Books.book_id,
                    Books.title,
                    Books.description,
                    Books.cover_url,
                    func.group_concat(Categories.name).label('category_names'),
                    Authors.name.label('author_name'),
                    ReadingHistory.last_position,
                    ReadingHistory.last_read_at,
                    func.coalesce(rating_subq.c.average_rating, 0).label('average_rating'),
                    func.coalesce(rating_subq.c.rating_count, 0).label('rating_count'),
                    rating_subq.c.last_rating_at
                )
                .outerjoin(t_book_categories, Books.book_id == t_book_categories.c.book_id)
                .outerjoin(Categories, t_book_categories.c.category_id == Categories.category_id)
                .outerjoin(Authors, Books.author_id == Authors.author_id)
                .outerjoin(ReadingHistory, (ReadingHistory.book_id == Books.book_id) & (ReadingHistory.user_id == session['user_id']))
                .outerjoin(rating_subq, rating_subq.c.book_id == Books.book_id)
                .filter(Books.book_id == book_id)
                .group_by(
                    Books.book_id,
                    Books.title,
                    Books.description,
                    Books.cover_url,
                    Authors.name,
                    ReadingHistory.last_position,
                    ReadingHistory.last_read_at,
                    rating_subq.c.average_rating,
                    rating_subq.c.rating_count,
                    rating_subq.c.last_rating_at
                )
            )
            # Số người đọc sách
            reader_count = (
                db_session.query(func.count(ReadingHistory.user_id))
                .filter(ReadingHistory.book_id == book_id)
                .scalar()
            )
            result = book_query.first()
            if not result:
                flash('Sách không tồn tại', 'danger')
                return redirect(url_for('user.library'))

            book_dict = {
                'book_id': result.book_id,
                'title': result.title,
                'description': result.description,
                'cover_url': result.cover_url,
                'category_names': result.category_names.replace(',', ', ') if result.category_names else '',
                'author_name': result.author_name,
                'last_position': result.last_position,
                'last_read_at': result.last_read_at,
                'average_rating': round(float(result.average_rating), 2) if result.average_rating else 0,
                'rating_count': result.rating_count,
                'last_rating_at': result.last_rating_at,
                'reader_count': reader_count or 0
            }

            return render_template('user/books/book_detail.html', book=book_dict, csrf_token=session.get('csrf_token'))

    except Exception as e:
        logger.error(f"Book detail error: {str(e)}", exc_info=True)
        flash('Lỗi khi xem chi tiết sách', 'danger')
        return redirect(url_for('user.library'))

# Đọc sách
@user_bp.route('/read/<int:book_id>')
@login_required
def read_book(book_id):
    try:
        with Session(engine) as db_session:
            book = db_session.query(Books).filter(Books.book_id == book_id).first()
            if not book:
                flash('Sách không tồn tại', 'danger')
                return redirect(url_for('user.library'))
            return redirect(url_for('user.read_from_position', book_id=book_id, position=0))
    except Exception as e:
        logger.error(f"Read book error: {str(e)}", exc_info=True)
        flash('Lỗi khi mở sách', 'danger')
        return redirect(url_for('user.library'))

@user_bp.route('/read/<int:book_id>/from/<int:position>')
@login_required
def read_from_position(book_id, position):
    try:
        with Session(engine) as db_session:
            book = db_session.query(Books).filter(Books.book_id == book_id).first()
            if not book:
                flash('Sách không tồn tại', 'danger')
                return redirect(url_for('user.library'))

            # Kiểm tra position hợp lệ
            if position < 0:
                position = 0
                flash('Vị trí đọc không hợp lệ, đặt lại về 0', 'warning')

            # Cập nhật vị trí đọc
            reading_history = ReadingHistory(
                user_id=session['user_id'],
                book_id=book_id,
                last_position=position,
                last_read_at=datetime.now()
            )
            db_session.merge(reading_history)
            db_session.commit()

            return render_template('user/books/read.html', book=book, start_position=position, csrf_token=session.get('csrf_token'))

    except Exception as e:
        logger.error(f"Read book error: {str(e)}", exc_info=True)
        flash('Lỗi khi mở sách', 'danger')
        return redirect(url_for('user.library'))

# Cập nhật vị trí đọc
@user_bp.route('/update-reading-position', methods=['POST'])
@login_required
def update_reading_position():
    try:
        data = request.get_json()
        book_id = int(data.get('book_id'))
        page = int(data.get('page'))

        # Kiểm tra dữ liệu đầu vào
        if page < 0:
            logger.warning(f"Invalid page number: {page}")
            return jsonify({'success': False, 'error': 'Trang không hợp lệ'}), 400

        with Session(engine) as db_session:
            # Kiểm tra book_id
            book = db_session.query(Books).filter(Books.book_id == book_id).first()
            if not book:
                logger.warning(f"Book not found: book_id={book_id}")
                return jsonify({'success': False, 'error': 'Sách không tồn tại'}), 404

            # Cập nhật hoặc tạo mới
            reading_history = ReadingHistory(
                user_id=session['user_id'],
                book_id=book_id,
                last_position=page,
                last_read_at=datetime.now()
            )
            db_session.merge(reading_history)
            db_session.commit()

            logger.info(f"Updated reading position: user_id={session['user_id']}, book_id={book_id}, page={page}")
            return jsonify({'success': True}), 200

    except ValueError:
        logger.warning(f"Invalid input data: book_id={book_id}, page={page}")
        return jsonify({'success': False, 'error': 'Dữ liệu không hợp lệ'}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'Lỗi server'}), 500

# Tìm kiếm sách
@user_bp.route('/search')
@login_required
def search():
    try:
        with Session(engine) as db_session:
            category_id = request.args.get('category_id', type=int)
            keyword = request.args.get('keyword', '').strip()
            page = request.args.get('page', 1, type=int)
            per_page = 12

            # Kiểm tra độ dài keyword
            if keyword and len(keyword) > 100:
                flash('Từ khóa tìm kiếm quá dài, vui lòng thử lại', 'warning')
                return redirect(url_for('user.library'))
            # Nếu cả keyword và category_id đều không có
            if not keyword and not category_id:
                flash('Vui lòng nhập từ khóa hoặc chọn thể loại để tìm kiếm.', 'danger')
                return render_template(
                    'user/books/search_results.html',
                    books=[],
                    current_category=None,
                    keyword='',
                    page=1,
                    total_pages=1,
                    total_books=0,
                    csrf_token=session.get('csrf_token')
                )
            # Nếu có category_id, kiểm tra tính hợp lệ
            if category_id:
                category = db_session.query(Categories).filter(Categories.category_id == category_id).first()
                if not category:
                    flash('Thể loại không tồn tại', 'warning')
                    return redirect(url_for('user.library'))

            # Subquery để lấy lịch sử đọc gần nhất
            subquery = (
                db_session.query(
                    ReadingHistory.book_id,
                    ReadingHistory.user_id,
                    ReadingHistory.last_position,
                    ReadingHistory.last_read_at
                )
                .filter(ReadingHistory.user_id == session['user_id'])
                .filter(
                    ReadingHistory.last_read_at == db_session.query(
                        func.max(ReadingHistory.last_read_at)
                    )
                    .filter(ReadingHistory.user_id == session['user_id'])
                    .filter(ReadingHistory.book_id == ReadingHistory.book_id)
                    .correlate(ReadingHistory)
                    .scalar_subquery()
                )
                .subquery()
            )

            # Truy vấn chính
            query = (
                db_session.query(
                    Books.book_id,
                    Books.title,
                    Books.cover_url,
                    Books.description,
                    func.group_concat(Categories.name).label('category_names'),
                    Authors.name.label('author_name'),
                    subquery.c.last_position,
                    subquery.c.last_read_at.label('last_read')
                )
                .outerjoin(t_book_categories, Books.book_id == t_book_categories.c.book_id)
                .outerjoin(Categories, t_book_categories.c.category_id == Categories.category_id)
                .outerjoin(Authors, Books.author_id == Authors.author_id)
                .outerjoin(subquery, Books.book_id == subquery.c.book_id)
            )

            if category_id:
                query = query.filter(t_book_categories.c.category_id == category_id)

            if keyword:
                keyword_param = f"%{keyword}%"
                query = query.filter(
                    or_(
                        Books.title.like(keyword_param),
                        Authors.name.like(keyword_param)
                    )
                )

            # Đếm tổng số sách
            count_query = query.group_by(Books.book_id, Authors.name, subquery.c.last_position, subquery.c.last_read_at)
            total_books = db_session.query(func.count()).select_from(count_query.subquery()).scalar()
            total_pages = (total_books + per_page - 1) // per_page

            # Phân trang
            offset = (page - 1) * per_page
            books_query = query.group_by(Books.book_id, Authors.name, subquery.c.last_position, subquery.c.last_read_at).order_by(Books.book_id.desc()).limit(per_page).offset(offset)
            books = [
                {
                    'book_id': book_id,
                    'title': title,
                    'cover_url': cover_url,
                    'description': description,
                    'category_names': category_names.replace(',', ', ') if category_names else '',
                    'author_name': author_name,
                    'last_position': last_position,
                    'last_read': last_read
                }
                for book_id, title, cover_url, description, category_names, author_name, last_position, last_read in books_query.all()
            ]

            # Nếu không có sách và page > 1, chuyển về trang 1
            if not books and page > 1:
                flash('Không tìm thấy sách ở trang này, quay lại trang đầu', 'info')
                return redirect(url_for('user.search', category_id=category_id, keyword=keyword, page=1))

            # Lấy thông tin thể loại hiện tại
            current_category = None
            if category_id:
                current_category = db_session.query(Categories).filter(Categories.category_id == category_id).first()
            all_categories = db_session.query(Categories).all()
            return render_template(
                'user/books/search_results.html',
                books=books,
                current_category=current_category,
                categories=all_categories,
                keyword=keyword,
                category_id=category_id,
                page=page,
                total_pages=total_pages,
                total_books=total_books,
                csrf_token=session.get('csrf_token')
            )

    except Exception as e:
        logger.error(f"Search error: {str(e)}", exc_info=True)
        flash('Lỗi khi tìm kiếm sách', 'danger')
        return redirect(url_for('user.library'))

# Gửi đánh giá sách
@user_bp.route('/submit_rating', methods=['POST'])
@login_required
def submit_rating():
    if request.headers.get('X-CSRFToken') != session.get('csrf_token'):
        return jsonify({'success': False, 'error': 'CSRF token không hợp lệ'})

    try:
        data = request.get_json()
        book_id = int(data.get('book_id'))
        rating = int(data.get('rating'))

        # Kiểm tra dữ liệu
        if not (1 <= rating <= 5):
            return jsonify({'success': False, 'error': 'Điểm đánh giá phải từ 1 đến 5'})

        with Session(engine) as db_session:
            # Kiểm tra sách tồn tại
            book = db_session.query(Books).filter(Books.book_id == book_id).first()
            if not book:
                return jsonify({'success': False, 'error': 'Sách không tồn tại'})

            existing_rating = db_session.query(Ratings).filter(
                and_(
                    Ratings.book_id == book_id,
                    Ratings.user_id == session['user_id']
                )
            ).first()
            if existing_rating:
                # Cập nhật rating và thời gian
                existing_rating.rating = rating
                existing_rating.created_at = datetime.now()
            else:
                # Tạo mới rating
                new_rating = Ratings(
                    user_id=session['user_id'],
                    book_id=book_id,
                    rating=rating,
                    created_at=datetime.now()
                )
                db_session.add(new_rating)
            db_session.commit()

            return jsonify({'success': True})

    except ValueError:
        return jsonify({'success': False, 'error': 'Dữ liệu không hợp lệ'})
    except Exception as e:
        logger.error(f"Submit rating error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})