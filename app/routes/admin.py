from flask import Blueprint, render_template, redirect, url_for, flash, request, session, send_from_directory
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import logging
from functools import wraps
from config import DB_CONFIG, UPLOAD_FOLDER
from app.models import Base, Books, Authors, Categories, t_book_categories, Ratings, Users, ReadingHistory  # Import models từ models.py
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from datetime import datetime, timedelta
admin_bp = Blueprint('admin', __name__)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tạo engine và session cho SQLAlchemy
engine = create_engine(f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")
Base.metadata.create_all(engine)  # Tạo bảng nếu chưa tồn tại

# Route để serve file upload
@admin_bp.route('/uploads/<path:subfolder>/<filename>')
def serve_uploaded_files(subfolder, filename):
    safe_subfolder = secure_filename(subfolder)
    safe_filename = secure_filename(filename)
    return send_from_directory(os.path.join(UPLOAD_FOLDER, safe_subfolder), safe_filename)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Truy cập bị từ chối: Yêu cầu quyền Admin', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file, subfolder):
    if file and allowed_file(file.filename):
        filename = f"{datetime.now().timestamp()}_{secure_filename(file.filename)}"
        upload_path = os.path.join(UPLOAD_FOLDER, subfolder)
        os.makedirs(upload_path, exist_ok=True)
        file_path = os.path.join(upload_path, filename)
        file.save(file_path)
        return f"uploads/{subfolder}/{filename}"
    return None

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    try:
        with Session(engine) as db_session:
            total_books = db_session.query(func.count(Books.book_id)).scalar()
            total_categories = db_session.query(func.count(Categories.category_id)).scalar()
            total_readers = db_session.query(func.count(Users.user_id)).filter(Users.role == 'reader').scalar()
            new_books = db_session.query(func.count(Books.book_id)).filter(Books.created_at >= datetime.now() - timedelta(days=7)).scalar()
            total_reads = db_session.query(func.count()).select_from(ReadingHistory).scalar()
            total_authors = db_session.query(func.count(Authors.author_id)).scalar()

            return render_template('admin/dashboard.html',
                                total_books=total_books,
                                total_categories=total_categories,
                                total_readers=total_readers,
                                new_books=new_books,
                                total_reads=total_reads,
                                total_authors=total_authors)
    except Exception as e:
        print(f"Lỗi khi thống kê dashboard: {e}")
        return render_template('admin/dashboard.html',
                                total_books=0,
                                total_categories=0,
                                total_readers=0,
                                new_books=0,
                                total_reads=0,
                                total_authors=0)

@admin_bp.route('/books')
@admin_required
def book_list():
    try:
        search_query = request.args.get('q', '').strip()
        category_id = request.args.get('category', None)

        with Session(engine) as db_session:
            # Truy vấn books với thông tin author và categories
            query = (
                db_session.query(
                    Books,
                    Authors.name.label('author_name'),
                    func.group_concat(Categories.name).label('category_names')
                )
                .outerjoin(Authors, Books.author_id == Authors.author_id)
                .outerjoin(t_book_categories, Books.book_id == t_book_categories.c.book_id)
                .outerjoin(Categories, t_book_categories.c.category_id == Categories.category_id)
            )

            if search_query:
                query = query.filter(
                    (Books.title.like(f"%{search_query}%")) |
                    (Authors.name.like(f"%{search_query}%"))
                )

            if category_id and category_id.isdigit():
                query = query.filter(t_book_categories.c.category_id == int(category_id))
                logger.debug(f"Filtering by category_id: {category_id}")
            else:
                logger.debug("No valid category_id provided")

            query = query.group_by(Books.book_id, Authors.name).order_by(Books.book_id.asc())
            books = [
                {**book.__dict__, 'author_name': author_name, 'category_names': category_names}
                for book, author_name, category_names in query.all()
            ]

            # Lấy danh sách categories cho dropdown
            categories = db_session.query(Categories).all()
            
            return render_template(
                'admin/books/list.html',
                books=books,
                categories=categories,
                search_query=search_query,
                selected_category=category_id
            )
    except Exception as e:
        logger.error(f"Book list error: {str(e)}")
        flash('Lỗi tải danh sách sách', 'danger')
        return render_template('admin/books/list.html', books=[], categories=[])

@admin_bp.route('/books/add', methods=['GET', 'POST'])
@admin_required
def add_book():
    if request.method == 'POST':
        try:
            with Session(engine) as db_session:
                # Xử lý upload file
                cover_url = save_file(request.files.get('cover'), 'covers')
                file_url = save_file(request.files.get('file'), 'books')

                # Validate dữ liệu
                if not request.form.get('title'):
                    flash('Tiêu đề sách không được trống', 'danger')
                    return redirect(url_for('admin.add_book'))

                # Xử lý tác giả
                author_name = request.form.get('author_name').strip()
                if not author_name:
                    flash('Tên tác giả không được trống', 'danger')
                    return redirect(url_for('admin.add_book'))

                existing_author = db_session.query(Authors).filter(Authors.name == author_name).first()
                if existing_author:
                    author_id = existing_author.author_id
                else:#Nếu chưa tồn tại thì thêm mới
                    new_author = Authors(name=author_name)
                    db_session.add(new_author)
                    db_session.flush() 
                    author_id = new_author.author_id

                # Xử lý năm xuất bản
                try:
                    published_year = int(request.form['published_year']) if request.form.get('published_year') else None
                except ValueError:
                    published_year = None
                    flash('Năm xuất bản phải là số', 'warning')

                # Thêm sách mới
                new_book = Books(
                    title=request.form['title'],
                    author_id=author_id,
                    cover_url=cover_url,
                    description=request.form.get('description', ''),
                    file_url=file_url,
                    published_year=published_year
                )
                db_session.add(new_book)
                db_session.flush() 

                # Xử lý nhiều thể loại
                category_ids = request.form.getlist('category_id')
                if category_ids:
                    for cat_id in category_ids:
                        db_session.execute(
                            t_book_categories.insert().values(book_id=new_book.book_id, category_id=cat_id)
                        )

                db_session.commit()
                flash('Thêm sách thành công!', 'success')
                return redirect(url_for('admin.book_list'))

        except Exception as e:
            logger.error(f"Add book error: {str(e)}", exc_info=True)
            flash(f'Lỗi khi thêm sách: {str(e)}', 'danger')
            return redirect(url_for('admin.add_book'))

    try:
        with Session(engine) as db_session:
            authors = db_session.query(Authors).all()
            categories = db_session.query(Categories).all()
            return render_template(
                'admin/books/add.html',
                authors=authors,
                categories=categories
            )
    except Exception as e:
        logger.error(f"Load form error: {str(e)}")
        flash('Lỗi tải dữ liệu form', 'danger')
        return redirect(url_for('admin.book_list'))

@admin_bp.route('/books/edit/<int:book_id>', methods=['GET', 'POST'])
@admin_required
def edit_book(book_id):
    try:
        with Session(engine) as db_session:
            # Lấy sách theo ID
            book = db_session.query(Books).filter_by(book_id=book_id).first()
            if not book:
                flash('Không tìm thấy sách', 'danger')
                return redirect(url_for('admin.book_list'))

            if request.method == 'POST':
                # Lấy dữ liệu từ form
                title = request.form.get('title', '').strip()
                author_name = request.form.get('author_name', '').strip()
                published_year = request.form.get('published_year', '').strip()
                description = request.form.get('description', '').strip()
                category_ids = request.form.getlist('category_id')

                # Kiểm tra tên và tác giả
                if not title or not author_name:
                    flash('Tên sách và tác giả là bắt buộc.', 'danger')
                    return redirect(url_for('admin.edit_book', book_id=book_id))

                # Xử lý tác giả: tạo mới nếu chưa có
                author = db_session.query(Authors).filter_by(name=author_name).first()
                if not author:
                    author = Authors(name=author_name)
                    db_session.add(author)
                    db_session.flush()  # Để lấy author_id
                book.author_id = author.author_id

                # Cập nhật thông tin sách
                book.title = title
                book.description = description
                book.published_year = int(published_year) if published_year.isdigit() else None

                # Upload ảnh bìa mới nếu có
                cover_file = request.files.get('cover')
                if cover_file and cover_file.filename:
                    new_cover = save_file(cover_file, 'covers')
                    if new_cover:
                        # Xoá ảnh cũ nếu tồn tại
                        if book.cover_url:
                            old_path = os.path.join(UPLOAD_FOLDER, book.cover_url.replace('uploads/', '').replace('/', os.sep))
                            if os.path.exists(old_path):
                                os.remove(old_path)
                        book.cover_url = new_cover

                # Upload file sách mới nếu có
                book_file = request.files.get('file')
                if book_file and book_file.filename:
                    new_file = save_file(book_file, 'books')
                    if new_file:
                        # Xoá file cũ nếu tồn tại
                        if book.file_url:
                            old_path = os.path.join(UPLOAD_FOLDER, book.file_url.replace('uploads/', '').replace('/', os.sep))
                            if os.path.exists(old_path):
                                os.remove(old_path)
                        book.file_url = new_file

                # Cập nhật thể loại: xoá cũ, thêm mới
                db_session.execute(
                    t_book_categories.delete().where(t_book_categories.c.book_id == book.book_id)
                )
                for cat_id in category_ids:
                    db_session.execute(
                        t_book_categories.insert().values(book_id=book.book_id, category_id=int(cat_id))
                    )

                db_session.commit()
                flash('Cập nhật sách thành công!', 'success')
                return redirect(url_for('admin.book_list'))

            # GET request: hiển thị form
            categories = db_session.query(Categories).all()
            current_categories = [cat.category_id for cat in book.category]
            book.author_name = book.author.name if book.author else ''
            return render_template(
                'admin/books/edit.html',
                book=book,
                categories=categories,
                current_categories=current_categories
            )
    except Exception as e:
        logger.error(f"Lỗi khi chỉnh sửa sách: {str(e)}")
        flash('Đã xảy ra lỗi khi chỉnh sửa sách.', 'danger')
        return redirect(url_for('admin.book_list'))


@admin_bp.route('/books/delete/<int:book_id>', methods=['POST'])
@admin_required
def delete_book(book_id):
    try:
        with Session(engine) as db_session:
            book = db_session.query(Books).filter(Books.book_id == book_id).first()
            if not book:
                flash('Không tìm thấy sách', 'danger')
                return redirect(url_for('admin.book_list'))

            # Xóa file liên quan
            for file_type in ['cover_url', 'file_url']:
                file_url = getattr(book, file_type)
                if file_url:
                    try:
                        relative_path = file_url.replace('uploads/', '')
                        file_path = os.path.join(UPLOAD_FOLDER, relative_path.replace('/', os.sep))
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        logger.error(f"Error deleting {file_type}: {str(e)}")

            db_session.delete(book)
            db_session.commit()

            flash('Xóa sách thành công!', 'success')
    except Exception as e:
        logger.error.error(f"Delete book error: {str(e)}")
        flash('Lỗi khi xóa sách', 'danger')
    return redirect(url_for('admin.book_list'))

@admin_bp.route('/books/view/<int:book_id>')
@admin_required
def view_book(book_id):
    try:
        with Session(engine) as db_session:
            # Truy vấn thông tin sách, tác giả và thể loại
            book_query = (
                db_session.query(
                    Books,
                    Authors.name.label('author_name'),
                    func.group_concat(Categories.name).label('category_names')
                )
                .outerjoin(Authors, Books.author_id == Authors.author_id)
                .outerjoin(t_book_categories, Books.book_id == t_book_categories.c.book_id)
                .outerjoin(Categories, t_book_categories.c.category_id == Categories.category_id)
                .filter(Books.book_id == book_id)
                .group_by(Books.book_id, Authors.name)
            )

            result = book_query.first()

            if not result:
                flash('Không tìm thấy sách', 'danger')
                return render_template('admin/books/view.html')

            book, author_name, category_names = result
            book_dict = book.__dict__
            book_dict['author_name'] = author_name
            book_dict['category_names'] = category_names

            # Truy vấn thống kê đánh giá
            rating_stats = (
                db_session.query(
                    func.count(Ratings.rating).label('rating_count'),
                    func.avg(Ratings.rating).label('average_rating'),
                    func.max(Ratings.created_at).label('latest_rating_update')
                )
                .filter(Ratings.book_id == book_id)
                .first()
            )

            if rating_stats:
                book_dict['rating_count'] = rating_stats.rating_count or 0
                book_dict['average_rating'] = round(rating_stats.average_rating, 2) if rating_stats.average_rating else None
                book_dict['latest_rating_update'] = rating_stats.latest_rating_update.strftime('%d/%m/%Y %H:%M') if rating_stats.latest_rating_update else None
            else:
                book_dict['rating_count'] = 0
                book_dict['average_rating'] = None
                book_dict['latest_rating_update'] = None

            # Thêm thống kê lượt đọc
            read_count = (
                db_session.query(func.count(ReadingHistory.user_id))
                .filter(ReadingHistory.book_id == book_id)
                .scalar()
            )
            book_dict['read_count'] = read_count or 0

            return render_template('admin/books/view.html', book=book_dict)

    except Exception as e:
        logger.error(f"View book error: {str(e)}")
        flash('Lỗi khi xem thông tin sách', 'danger')
        return redirect(url_for('admin.book_list'))
