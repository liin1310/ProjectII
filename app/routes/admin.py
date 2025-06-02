from flask import Blueprint, render_template, redirect, url_for, flash, request, session, send_from_directory
from werkzeug.utils import secure_filename
import os
import mysql.connector
from datetime import datetime
import logging
from functools import wraps
from config import DB_CONFIG, UPLOAD_FOLDER

admin_bp = Blueprint('admin', __name__)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Route để serve file upload
@admin_bp.route('/uploads/<path:subfolder>/<filename>')
def serve_uploaded_files(subfolder, filename):
    # Đảm bảo đường dẫn an toàn
    safe_subfolder = secure_filename(subfolder)
    safe_filename = secure_filename(filename)
    return send_from_directory(os.path.join(UPLOAD_FOLDER, safe_subfolder), safe_filename)
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Truy cập bị từ chối: Yêu cầu quyền Admin', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_file(file, subfolder):
    if file and allowed_file(file.filename):
        filename = f"{datetime.now().timestamp()}_{secure_filename(file.filename)}"
        upload_path = os.path.join(UPLOAD_FOLDER, subfolder)
        
        # Tạo thư mục nếu chưa tồn tại
        os.makedirs(upload_path, exist_ok=True)
        
        # Lưu file
        file_path = os.path.join(upload_path, filename)
        file.save(file_path)
        
        # Trả về đường dẫn tương đối để lưu trong DB
        return f"uploads/{subfolder}/{filename}"
    return None
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    return render_template('admin/dashboard.html')

@admin_bp.route('/books')
@admin_required
def book_list():
    try:
        search_query = request.args.get('q', '').strip()
        category_id = request.args.get('category', '')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT b.*, a.name as author_name, GROUP_CONCAT(c.name SEPARATOR ', ') as category_names
            FROM books b
            LEFT JOIN authors a ON b.author_id = a.author_id
            LEFT JOIN book_categories bc ON b.book_id = bc.book_id
            LEFT JOIN categories c ON bc.category_id = c.category_id
            WHERE 1=1
        """
        params = []

        if search_query:
            query += " AND (b.title LIKE %s OR a.name LIKE %s)"
            params.extend([f"%{search_query}%", f"%{search_query}%"])

        if category_id:
            query += " AND b.category_id = %s"
            params.append(category_id)

        query += " GROUP BY b.book_id, a.name ORDER BY b.book_id ASC"
        
        cursor.execute(query, params)
        books = cursor.fetchall()

        # Lấy danh sách categories cho dropdown
        cursor.execute("SELECT category_id, name FROM categories")
        categories = cursor.fetchall()

        return render_template('admin/books/list.html', 
                            books=books,
                            categories=categories)
    except Exception as e:
        logger.error(f"Book list error: {str(e)}")
        flash('Lỗi tải danh sách sách', 'error')
        return render_template('admin/books/list.html', books=[], categories=[])
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/books/add', methods=['GET', 'POST'])
@admin_required
def add_book():
    if request.method == 'POST':
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Xử lý upload file
            cover_url = save_file(request.files.get('cover'), 'covers')
            file_url = save_file(request.files.get('file'), 'books')
            
            # Validate dữ liệu
            if not request.form.get('title'):
                flash('Tiêu đề sách không được trống', 'error')
                return redirect(url_for('admin.add_book'))

            # Xử lý tác giả
            author_name = request.form.get('author_name').strip()
            if not author_name:
                flash('Tên tác giả không được trống', 'error')
                return redirect(url_for('admin.add_book'))

            cursor.execute("SELECT author_id FROM authors WHERE name = %s", (author_name,))
            existing_author = cursor.fetchone()
            
            if existing_author:
                author_id = existing_author['author_id']
            else:
                cursor.execute("INSERT INTO authors (name) VALUES (%s)", (author_name,))
                author_id = cursor.lastrowid
                conn.commit()

            # Xử lý năm xuất bản
            try:
                published_year = int(request.form['published_year']) if request.form.get('published_year') else None
            except ValueError:
                published_year = None
                flash('Năm xuất bản phải là số', 'warning')

            # Thêm sách mới
            cursor.execute("""
                INSERT INTO books (
                    title, author_id, 
                    cover_url, description, file_url, published_year
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                request.form['title'],
                author_id,
                cover_url,
                request.form.get('description', ''),
                file_url,
                published_year
            ))
            book_id = cursor.lastrowid
            conn.commit()
            # Xử lý nhiều thể loại
            category_ids = request.form.getlist('category_id')  # Lấy danh sách category_id từ form
            if category_ids:
                for cat_id in category_ids:
                    cursor.execute("""
                        INSERT INTO book_categories (book_id, category_id)
                        VALUES (%s, %s)
                    """, (book_id, cat_id))
                conn.commit()
            flash('Thêm sách thành công!', 'success')
            return redirect(url_for('admin.book_list'))
            
        except Exception as e:
            logger.error(f"Add book error: {str(e)}", exc_info=True)
            flash(f'Lỗi khi thêm sách: {str(e)}', 'error')
            if conn:
                conn.rollback()
            return redirect(url_for('admin.add_book'))
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT author_id, name FROM authors")
        authors = cursor.fetchall()
        cursor.execute("SELECT category_id, name FROM categories")
        categories = cursor.fetchall()
        return render_template('admin/books/add.html', 
                            authors=authors, 
                            categories=categories)
    except Exception as e:
        logger.error(f"Load form error: {str(e)}")
        flash('Lỗi tải dữ liệu form', 'error')
        return redirect(url_for('admin.book_list'))
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/books/edit/<int:book_id>', methods=['GET', 'POST'])
@admin_required
def edit_book(book_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'POST':
            cursor.execute("""
                UPDATE books SET
                    title = %s,
                    author_id = %s,
                    description = %s,
                    published_year = %s
                WHERE book_id = %s
            """, (
                request.form['title'],
                request.form['author_id'],
                request.form.get('description', ''),
                request.form.get('published_year'),
                book_id
            ))
            
            if 'cover' in request.files and request.files['cover'].filename:
                new_cover = save_file(request.files['cover'], 'covers')
                if new_cover:
                    cursor.execute("UPDATE books SET cover_url = %s WHERE book_id = %s", 
                                 (new_cover, book_id))
            
            # Xóa các thể loại cũ và thêm thể loại mới
            cursor.execute("DELETE FROM book_categories WHERE book_id = %s", (book_id,))
            category_ids = request.form.getlist('category_id')
            if category_ids:
                for cat_id in category_ids:
                    cursor.execute("""
                        INSERT INTO book_categories (book_id, category_id)
                        VALUES (%s, %s)
                    """, (book_id, cat_id))
        
            conn.commit()
            flash('Cập nhật sách thành công!', 'success')
            return redirect(url_for('admin.book_list'))
        
        cursor.execute("SELECT * FROM books WHERE book_id = %s ", (book_id,))
        book = cursor.fetchone()
        
        cursor.execute("SELECT author_id, name FROM authors")
        authors = cursor.fetchall()
        
        cursor.execute("SELECT category_id, name FROM categories")
        categories = cursor.fetchall()
        
        # Lấy danh sách thể loại hiện tại của sách
        cursor.execute("""
            SELECT category_id FROM book_categories WHERE book_id = %s
        """, (book_id,))
        current_categories = [row['category_id'] for row in cursor.fetchall()]

        return render_template('admin/books/edit.html',
                            book=book,
                            authors=authors,
                            categories=categories,
                            current_categories=current_categories)
            
    except Exception as e:
        logger.error(f"Edit book error: {str(e)}")
        flash('Lỗi khi cập nhật sách', 'error')
        return redirect(url_for('admin.book_list'))
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/books/delete/<int:book_id>', methods=['POST'])
@admin_required
def delete_book(book_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT cover_url, file_url FROM books WHERE book_id = %s", (book_id,))
        book = cursor.fetchone()
        
        cursor.execute("DELETE FROM books WHERE book_id = %s", (book_id,))
        conn.commit()
        
        if book:
            for file_type in ['cover_url', 'file_url']:
                if book[file_type]:
                    try:
                        # Lấy phần đường dẫn sau 'uploads/'
                        relative_path = book[file_type].replace('uploads/','')
                        file_path = os.path.join(UPLOAD_FOLDER, relative_path.replace('/', os.sep))
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        logger.error(f"Error deleting {file_type}: {str(e)}")

        flash('Xóa sách thành công!', 'success')
    except Exception as e:
        logger.error(f"Delete book error: {str(e)}")
        flash('Lỗi khi xóa sách', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin.book_list'))

@admin_bp.route('/books/view/<int:book_id>')
@admin_required
def view_book(book_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary = True)
        cursor.execute("""
            SELECT b.*, a.name as author_name, GROUP_CONCAT(c.name SEPARATOR ', ') as category_names
            FROM books b
            LEFT JOIN authors a ON b.author_id = a.author_id
            LEFT JOIN book_categories bc ON b.book_id = bc.book_id
            LEFT JOIN categories c ON b.category_id = c.category_id
            WHERE b.book_id = %s
            GROUP BY b.book_id, a.name
        """, (book_id,))
        
        book = cursor.fetchone()
        if not book:
            flash('Không tìm thấy sách','error')
            return render_template('admin/books/view.html')
        return render_template('admin/books/view.html', book = book)
    except Exception as e:
        logger.error(f"View book error: {str(e)}")
        flash('Lỗi khi xem thông tin sách', 'error')
        return redirect(url_for('admin.book_list'))
    finally:
        cursor.close()
        conn.close()

