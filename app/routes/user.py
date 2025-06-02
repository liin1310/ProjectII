from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
import mysql.connector  
from config import DB_CONFIG
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import logging
import secrets

user_bp = Blueprint('user', __name__)

# Tạo logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) 

# Yêu cầu đăng nhập
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Vui lòng đăng nhập.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Kiểm tra CSRF token
def check_csrf_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            if request.headers.get('X-CSRFToken') != session.get('csrf_token'):
                if request.is_json:
                    return jsonify({'success': False, 'error': 'CSRF token không hợp lệ'})
                flash('CSRF token không hợp lệ', 'error')
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

# Quản lý tài khoản
    # Xem thông tin
@user_bp.route('/profile')
@login_required
def profile():
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
        user = cursor.fetchone()
        return render_template('user/profile/profile.html', user=user)
    except Exception as e:
        logger.error(f"Profile error: {str(e)}", exc_info=True)
        flash('Lỗi khi tải thông tin người dùng', 'error')
        return redirect(url_for('auth.login'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    # Cập nhật thông tin
@user_bp.route('/updateProfile', methods=['GET', 'POST'])
@login_required
@check_csrf_token
def updateProfile():
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            fullname = request.form.get('fullname', '').strip()
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip().lower()
            age = int(request.form['age'])

            # Kiểm tra email trùng
            cursor.execute("""
                SELECT user_id FROM users 
                WHERE email = %s AND user_id != %s
            """, (email, session['user_id']))
            if cursor.fetchone():
                flash('Email đã được sử dụng bởi tài khoản khác!', 'error')
                user = {'fullname': fullname, 'username': username, 'age': age, 'email': email}
                return render_template('user/profile/updateProfile.html', user=user)

            cursor.execute("""
                UPDATE users 
                SET fullname = %s, age = %s, email = %s, username = %s
                WHERE user_id = %s
            """, (fullname, age, email, username, session['user_id']))
            conn.commit()

            flash('Cập nhật thông tin thành công!', 'success')
            refresh_csrf_token()
            return redirect(url_for('user.profile'))

        else:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
            user = cursor.fetchone()
            return render_template('user/profile/updateProfile.html', user=user)

    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        flash(f'Lỗi cơ sở dữ liệu: {err}', 'error')
        return render_template('user/profile/updateProfile.html', user={})

    except Exception as err:
        flash(f'Lỗi hệ thống: {err}', 'error')
        return render_template('user/profile/updateProfile.html', user={})

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # Thay đổi mật khẩu
@user_bp.route('/changePassword', methods=['GET', 'POST'])
@login_required
def changePassword():
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            old_password = request.form['old_password']
            new_password = request.form['new_password']
            # Kiểm tra độ dài new_password
            if len(new_password) < 6:
                flash("Mật khẩu dài ít nhất 6 kí tự", "error")
                return redirect(url_for('user.changePassword'))
            # Kiểm tra confirm_password có khác new_password không
            if new_password != request.form['confirm_password']:
                flash("Mật khẩu xác nhận không khớp", "error")
                return redirect(url_for('user.changePassword'))
            # Kiểm tra password có trùng với new_password không
            if new_password == old_password:
                flash("Mật khẩu mới không được trùng với mật khẩu cũ!", "error")
                return redirect(url_for('user.changePassword'))
            
            user_id = int(session['user_id'])
            # Kiểm tra nhập mật khẩu cũ đúng chưa
            cursor.execute("SELECT user_id, email, password FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            if not check_password_hash(user['password'], old_password):
                flash("Mật khẩu không chính xác", "error")
                return redirect(url_for('user.changePassword'))
            # Cập nhật thông tin
            hashed_password = generate_password_hash(new_password)
            cursor.execute("""
                UPDATE users 
                SET password = %s
                WHERE user_id = %s
            """, (hashed_password, user_id))
            conn.commit()

            flash('Cập nhật mật khẩu thành công! Vui lòng đăng nhập lại.', 'success')
            session.clear()
            refresh_csrf_token()
            return redirect(url_for('auth.login'))
        else:
            return render_template("user/profile/changePassword.html")
        
    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        flash(f'Lỗi cơ sở dữ liệu: {err}', 'error')
        return render_template('user/profile/changePassword.html', user={})

    except Exception as err:
        flash(f'Lỗi hệ thống: {err}', 'error')
        return render_template('user/profile/changePassword.html', user={})

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

#----------------------------------------------------------------------------------------------------------------------------------

@user_bp.app_context_processor
def inject_categories():
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT category_id, name FROM categories ORDER BY name")
        categories = cursor.fetchall()
        return {'categories': categories}
    except Exception as e:
        logger.error(f"Error loading categories: {str(e)}", exc_info=True)
        return {'categories': []}
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

# Xem danh sách sách
@user_bp.route('/library')
@login_required
def library():
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT b.book_id, b.title, b.cover_url, 
                   a.name AS author_name, 
                   GROUP_CONCAT(c.name SEPARATOR ', ') AS category_names,
                   rh.last_position,
                   rh.last_read_at AS last_read
            FROM books b
            LEFT JOIN authors a ON b.author_id = a.author_id
            LEFT JOIN book_categories bc ON b.book_id = bc.book_id
            LEFT JOIN categories c ON bc.category_id = c.category_id
            LEFT JOIN (
                SELECT book_id, user_id, last_position, last_read_at
                FROM reading_history
                WHERE user_id = %s
                AND last_read_at = (
                    SELECT MAX(last_read_at)
                    FROM reading_history rh2
                    WHERE rh2.book_id = reading_history.book_id
                    AND rh2.user_id = %s
                )
            ) rh ON b.book_id = rh.book_id
            GROUP BY b.book_id, a.name, rh.last_position, rh.last_read_at
        """, (session['user_id'], session['user_id']))
        
        books = cursor.fetchall()
        logger.info(f"Rendering library for user_id: {session['user_id']}")
        return render_template('user/books/library.html', books=books)
        
    except Exception as e:
        logger.error(f"Library error: {str(e)}", exc_info=True)
        flash('Lỗi khi tải thư viện sách', 'error')
        return redirect(url_for('auth.index'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# Xem chi tiết sách
@user_bp.route('/book/<int:book_id>')
@login_required
def book_detail(book_id):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT b.book_id, b.title, b.description, b.cover_url, 
                   GROUP_CONCAT(c.name SEPARATOR ', ') AS category_names, a.name AS author_name,
                   rh.last_position, rh.last_read_at,
                   COALESCE((SELECT AVG(rating) FROM ratings WHERE book_id = b.book_id), 0) AS average_rating,
                   COALESCE((SELECT COUNT(*) FROM ratings WHERE book_id = b.book_id), 0) AS rating_count
            FROM books b
            LEFT JOIN book_categories bc ON b.book_id = bc.book_id
            LEFT JOIN categories c ON bc.category_id = c.category_id
            LEFT JOIN authors a ON b.author_id = a.author_id
            LEFT JOIN reading_history rh ON rh.book_id = b.book_id AND rh.user_id = %s
            WHERE b.book_id = %s
            GROUP BY b.book_id, a.name, rh.last_position, rh.last_read_at
        """, (session.get('user_id'), book_id))
        book = cursor.fetchone()
        cursor.fetchall()
        if not book:
            flash('Sách không tồn tại', 'error')
            return redirect(url_for('user.library'))

        return render_template('user/books/book_detail.html', book=book, csrf_token=session['csrf_token'])

    except Exception as e:
        logger.error(f"Book detail error: {str(e)}", exc_info=True)
        flash('Lỗi khi xem chi tiết sách', 'error')
        return redirect(url_for('user.library'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# Đọc sách
@user_bp.route('/read/<int:book_id>')
@login_required
def read_book(book_id):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT 1 FROM books WHERE book_id = %s", (book_id,))
        if not cursor.fetchone():
            flash('Sách không tồn tại', 'error')
            return redirect(url_for('user.library'))
        return redirect(url_for('user.read_from_position', book_id=book_id, position=0))
    except Exception as e:
        logger.error(f"Read book error: {str(e)}", exc_info=True)
        flash('Lỗi khi mở sách', 'error')
        return redirect(url_for('user.library'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@user_bp.route('/read/<int:book_id>/from/<int:position>')
@login_required
def read_from_position(book_id, position):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        # Kiểm tra position hợp lệ
        if position < 0:
            position = 0
            flash('Vị trí đọc không hợp lệ, đặt lại về 0', 'warning')
        
        # Cập nhật vị trí đọc
        cursor.execute("""
            INSERT INTO reading_history (user_id, book_id, last_read_at, last_position)
            VALUES (%s, %s, NOW(), %s)
            ON DUPLICATE KEY UPDATE 
                last_read_at = NOW(),
                last_position = VALUES(last_position)
        """, (session['user_id'], book_id, position))
        conn.commit()
        
        # Lấy nội dung sách
        cursor.execute("SELECT * FROM books WHERE book_id = %s", (book_id,))
        book = cursor.fetchone()
        
        if not book:
            flash('Sách không tồn tại', 'error')
            return redirect(url_for('user.library'))
            
        return render_template('user/books/read.html', 
                            book=book,
                            start_position=position)
        
    except Exception as e:
        logger.error(f"Read book error: {str(e)}", exc_info=True)
        flash('Lỗi khi mở sách', 'error')
        return redirect(url_for('user.library'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@user_bp.route('/update-reading-position', methods=['POST'])
@login_required
def update_reading_position():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        book_id = data.get('book_id')
        page = data.get('page')

        # Kiểm tra dữ liệu đầu vào
        if not book_id or not isinstance(book_id, (int, str)) or not page or not isinstance(page, (int, str)):
            logger.warning(f"Invalid input data: book_id={book_id}, page={page}")
            return jsonify({'success': False, 'error': 'Dữ liệu không hợp lệ'}), 400
        book_id = int(book_id)
        page = int(page)
        if page < 0:
            logger.warning(f"Invalid page number: {page}")
            return jsonify({'success': False, 'error': 'Trang không hợp lệ'}), 400

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Kiểm tra book_id
        cursor.execute("SELECT COUNT(*) FROM books WHERE book_id = %s", (book_id,))
        if cursor.fetchone()[0] == 0:
            logger.warning(f"Book not found: book_id={book_id}")
            return jsonify({'success': False, 'error': 'Sách không tồn tại'}), 404

        # Lấy user_id
        user_id = session['user_id']  # Giả sử User model có id

        # Cập nhật hoặc tạo mới
        cursor.execute("""
            INSERT INTO reading_history (user_id, book_id, last_position)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE last_position = %s
        """, (user_id, book_id, page, page))
        conn.commit()

        logger.info(f"Updated reading position: user_id={user_id}, book_id={book_id}, page={page}")
        return jsonify({'success': True}), 200

    except mysql.connector.Error as db_err:
        logger.error(f"Database error: {str(db_err)}", exc_info=True)
        return jsonify({'success': False, 'error': 'Lỗi cơ sở dữ liệu'}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'Lỗi server'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@user_bp.route('/search')
@login_required
def search():
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        category_id = request.args.get('category_id', type=int)
        keyword = request.args.get('keyword', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = 12

        # Kiểm tra độ dài keyword
        if keyword and len(keyword) > 100:
            flash('Từ khóa tìm kiếm quá dài, vui lòng thử lại', 'warning')
            return redirect(url_for('user.library'))

        conditions = []
        params = []

        # Nếu có category_id, kiểm tra tính hợp lệ
        if category_id:
            cursor.execute("SELECT 1 FROM categories WHERE category_id = %s", (category_id,))
            if not cursor.fetchone():
                flash('Thể loại không tồn tại', 'warning')
                return redirect(url_for('user.library'))
            conditions.append("bc.category_id = %s")
            params.append(category_id)

        # Nếu có từ khoá
        if keyword:
            keyword_param = f"%{keyword}%"
            search_conditions = [
                "COALESCE(b.title, '') LIKE %s",
                "COALESCE(a.name, '') LIKE %s"
            ]
            conditions.append(f"({' OR '.join(search_conditions)})")
            params.extend([keyword_param, keyword_param])

        # Query để đếm tổng số sách và lấy dữ liệu phân trang
        base_query = """
            SELECT b.book_id, b.title, b.cover_url, b.description, 
                   GROUP_CONCAT(c.name SEPARATOR ', ') AS category_names, a.name AS author_name
            FROM books b
            LEFT JOIN book_categories bc ON b.book_id = bc.book_id
            LEFT JOIN categories c ON bc.category_id = c.category_id
            LEFT JOIN authors a ON b.author_id = a.author_id
        """
        if conditions:
            base_query += f" WHERE {' AND '.join(conditions)}"
        
        # Đếm tổng số sách
        count_query = f"SELECT COUNT(DISTINCT subquery.book_id) as total FROM ({base_query} GROUP BY b.book_id, a.name) AS subquery"

        # count_query = f"SELECT COUNT(DISTINCT b.book_id) as total FROM ({base_query}) AS subquery"
        cursor.execute(count_query, params)
        total_books = cursor.fetchone()['total']
        total_pages = (total_books + per_page - 1) // per_page

        # Lấy dữ liệu phân trang
        offset = (page - 1) * per_page
        paginated_query = f"{base_query} GROUP BY b.book_id, a.name HAVING b.book_id IS NOT NULL ORDER BY b.book_id DESC LIMIT %s OFFSET %s"
        params_paginated = params.copy()
        params_paginated.extend([per_page, offset])
        cursor.execute(paginated_query, params_paginated)
        books = cursor.fetchall()

        # Nếu không có sách và page > 1, chuyển về trang 1
        if not books and page > 1:
            flash('Không tìm thấy sách ở trang này, quay lại trang đầu', 'info')
            return redirect(url_for('user.search', category_id=category_id, keyword=keyword, page=1))

        # Lấy thông tin thể loại hiện tại
        current_category = None
        if category_id:
            cursor.execute("SELECT name FROM categories WHERE category_id = %s", (category_id,))
            current_category = cursor.fetchone()

        # Debug
        print("Final Query:", paginated_query)
        print("Query Params:", params_paginated)

        return render_template('user/books/search_results.html',
                               books=books,
                               current_category=current_category,
                               keyword=keyword,
                               page=page,
                               total_pages=total_pages,
                               total_books=total_books)

    except Exception as e:
        logger.error(f"Search error: {str(e)}", exc_info=True)
        flash('Lỗi khi tìm kiếm sách', 'error')
        return redirect(url_for('user.library'))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@user_bp.route('/submit_rating', methods=['POST'])
@login_required
def submit_rating():
    if request.headers.get('X-CSRFToken') != session.get('csrf_token'):
        return jsonify({'success': False, 'error': 'CSRF token không hợp lệ'})
    conn = None
    cursor = None
    try:
        data = request.get_json()
        book_id = int(data.get('book_id'))
        rating = int(data.get('rating'))

        # Kiểm tra dữ liệu
        if not (1 <= rating <= 5):
            return jsonify({'success': False, 'error': 'Điểm đánh giá phải từ 1 đến 5'})

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Chèn hoặc cập nhật đánh giá
        cursor.execute("""
            INSERT INTO ratings (user_id, book_id, rating)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE rating = %s
        """, (session.get('user_id'), book_id, rating, rating))
        conn.commit()

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Submit rating error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
