from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from app.models import db, Course, Category, User, Review, Image
from app.tools import CoursesFilter, ImageSaver

bp = Blueprint('courses', __name__, url_prefix='/courses')

COURSE_PARAMS = [
    'author_id', 'name', 'category_id', 'short_desc', 'full_desc'
]

def params():
    return { p: request.form.get(p) or None for p in COURSE_PARAMS }

def search_params():
    return {
        'name': request.args.get('name'),
        'category_ids': [x for x in request.args.getlist('category_ids') if x],
    }

@bp.route('/')
def index():
    courses = CoursesFilter(**search_params()).perform()
    pagination = db.paginate(courses)
    courses = pagination.items
    categories = db.session.execute(db.select(Category)).scalars()
    return render_template('courses/index.html',
                           courses=courses,
                           categories=categories,
                           pagination=pagination,
                           search_params=search_params())

@bp.route('/new')
@login_required
def new():
    course = Course()
    categories = db.session.execute(db.select(Category)).scalars()
    users = db.session.execute(db.select(User)).scalars()
    return render_template('courses/new.html',
                           categories=categories,
                           users=users,
                           course=course)

@bp.route('/create', methods=['POST'])
@login_required
def create():
    # Проверка, что category_id передаётся и не пустой
    category_id = request.form.get('category_id')
    if not category_id:
        flash('Выберите категорию курса!', 'danger')
        categories = db.session.execute(db.select(Category)).scalars()
        users = db.session.execute(db.select(User)).scalars()
        return render_template('courses/new.html', 
                              categories=categories,
                              users=users,
                              course=Course(**params()))
    
    f = request.files.get('background_img')
    img = None
    course = Course()
    try:
        if f and f.filename:
            img = ImageSaver(f).save()

        image_id = img.id if img else None
        course = Course(**params(), background_image_id=image_id)
        db.session.add(course)
        db.session.commit()
    except IntegrityError as err:
        flash(f'Возникла ошибка при записи данных в БД. Проверьте корректность введённых данных. ({err})', 'danger')
        db.session.rollback()
        categories = db.session.execute(db.select(Category)).scalars()
        users = db.session.execute(db.select(User)).scalars()
        return render_template('courses/new.html',
                            categories=categories,
                            users=users,
                            course=course)

    flash(f'Курс {course.name} был успешно добавлен!', 'success')

    return redirect(url_for('courses.index'))

@bp.route('/<int:course_id>')
def show(course_id):
    course = db.get_or_404(Course, course_id)
    
    # Получаем последние 5 отзывов
    latest_reviews = db.session.execute(
        db.select(Review)
        .filter(Review.course_id == course_id)
        .order_by(Review.created_at.desc())
        .limit(5)
    ).scalars().all()
    
    # Проверяем, оставил ли текущий пользователь отзыв
    user_review = None
    if current_user.is_authenticated:
        user_review = db.session.execute(
            db.select(Review).filter(
                Review.course_id == course_id,
                Review.user_id == current_user.id
            )
        ).scalar()
    
    return render_template('courses/show.html', 
                           course=course, 
                           latest_reviews=latest_reviews,
                           user_review=user_review)

@bp.route('/<int:course_id>/reviews')
def reviews(course_id):
    course = db.get_or_404(Course, course_id)
    
    # Получаем параметр сортировки
    sort_order = request.args.get('sort', 'newest')
    
    # Запрос для получения отзывов
    reviews_query = db.select(Review).filter(Review.course_id == course_id)
    
    # Применяем фильтрацию
    if sort_order == 'positive':
        reviews_query = reviews_query.order_by(Review.rating.desc())
    elif sort_order == 'negative':
        reviews_query = reviews_query.order_by(Review.rating.asc())
    else:  # newest
        reviews_query = reviews_query.order_by(Review.created_at.desc())
    
    # Пагинация
    pagination = db.paginate(reviews_query, per_page=5)
    reviews = pagination.items
    
    # Проверяем, оставил ли текущий пользователь отзыв
    user_review = None
    if current_user.is_authenticated:
        user_review = db.session.execute(
            db.select(Review).filter(
                Review.course_id == course_id,
                Review.user_id == current_user.id
            )
        ).scalar()
    
    return render_template('courses/reviews.html',
                           course=course,
                           reviews=reviews,
                           pagination=pagination,
                           sort_order=sort_order,
                           user_review=user_review)

@bp.route('/<int:course_id>/add_review', methods=['POST'])
@login_required
def add_review(course_id):
    course = db.get_or_404(Course, course_id)
    
    # Проверяем, есть ли уже отзыв от данного пользователя
    existing_review = db.session.execute(
        db.select(Review).filter(
            Review.course_id == course_id,
            Review.user_id == current_user.id
        )
    ).scalar()
    
    if existing_review:
        flash('Вы уже оставили отзыв к этому курсу', 'warning')
        return redirect(url_for('courses.show', course_id=course_id))
    
    # Получаем данные из формы
    rating = int(request.form.get('rating', 5))
    text = request.form.get('text', '')
    
    # Валидация
    if not (0 <= rating <= 5):
        flash('Оценка должна быть в диапазоне от 0 до 5', 'danger')
        return redirect(url_for('courses.show', course_id=course_id))
    
    if not text:
        flash('Текст отзыва не может быть пустым', 'danger')
        return redirect(url_for('courses.show', course_id=course_id))
    
    # Создаем новый отзыв
    review = Review(
        rating=rating,
        text=text,
        course_id=course_id,
        user_id=current_user.id
    )
    
    try:
        db.session.add(review)
        
        # Обновляем рейтинг курса
        course.rating_sum += rating
        course.rating_num += 1
        
        db.session.commit()
        flash('Ваш отзыв успешно добавлен', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла ошибка при добавлении отзыва: {str(e)}', 'danger')
    
    # Получаем URL источника запроса для возврата на нужную страницу
    referer = request.referrer
    if referer and 'reviews' in referer:
        return redirect(url_for('courses.reviews', course_id=course_id))
    else:
        return redirect(url_for('courses.show', course_id=course_id))