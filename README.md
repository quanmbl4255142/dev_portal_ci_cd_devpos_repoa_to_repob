# 🚀 Django Dev Portal

**Django Dev Portal** là một công cụ tự động tạo Django REST API Project với đầy đủ cấu trúc, CI/CD pipeline và ArgoCD integration. Chỉ cần nhập thông tin vào web UI đẹp mắt, và bạn sẽ có ngay một Django project production-ready!

![Django Dev Portal](https://img.shields.io/badge/Django-Dev%20Portal-purple?style=for-the-badge&logo=django)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)

## ✨ Tính năng

- 🎨 **UI đẹp và hiện đại** - Giao diện web thân thiện với Tailwind CSS
- ⚡ **Tự động sinh code** - Tạo Django project với models, views, serializers, URLs
- 🐳 **Docker ready** - Dockerfile và docker-compose đã sẵn sàng
- 🔄 **CI/CD tích hợp** - GitHub Actions workflow tự động
- 📦 **ArgoCD support** - Tự động update k8s manifests
- 🌐 **REST API đầy đủ** - CRUD operations cho tất cả models
- 🔐 **CORS enabled** - Sẵn sàng cho frontend integration
- 📊 **Health check endpoint** - Monitor application status

## 📋 Yêu cầu

- Python 3.11+
- Docker (optional)
- Git

## 🚀 Cài đặt & Chạy

### Cách 1: Chạy trực tiếp với Python

```bash
# Clone repository
cd dev-portal-service

# Cài đặt dependencies
pip install -r requirements.txt

# Chạy server
python main.py
```

### Cách 2: Chạy với Docker

```bash
cd dev-portal-service

# Build Docker image
docker build -t django-dev-portal .

# Run container
docker run -p 8080:8080 django-dev-portal
```

### Cách 3: Chạy với Docker Compose

```bash
cd dev-portal-service

# Start service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop service
docker-compose down
```

Sau khi chạy, truy cập: **http://localhost:8080**

## 📖 Hướng dẫn sử dụng

### Bước 1: Cấu hình Project

1. **Tên Django Project**: Tên project chính (vd: `django_api`, `my_project`)
2. **Tên Django App**: Tên app chứa models (vd: `api`, `core`)
3. **GitHub Username**: Username GitHub của bạn (optional)
4. **Git Repository URL**: URL của repository (optional)
5. **Docker Registry**: Registry để push images (mặc định: `ghcr.io`)
6. **Repository_B URL**: URL của repo chứa k8s manifests (optional)

### Bước 2: Định nghĩa Models

1. Click **"Thêm Model"** để tạo model mới
2. Nhập:
   - **Tên Model**: Tên class model (PascalCase, vd: `Product`, `User`)
   - **API Endpoint**: URL path (lowercase, vd: `products`, `users`)

### Bước 3: Thêm Fields cho Model

1. Click **"Thêm Field"** trong mỗi model
2. Chọn:
   - **Tên Field**: Tên field (vd: `name`, `price`, `description`)
   - **Loại**: Chọn Django field type:
     - `CharField` - Text ngắn
     - `TextField` - Text dài
     - `IntegerField` - Số nguyên
     - `DecimalField` - Số thập phân
     - `BooleanField` - True/False
     - `DateField` - Ngày
     - `DateTimeField` - Ngày giờ
     - `EmailField` - Email
     - `URLField` - URL
     - Và nhiều loại khác...
   - **Options**:
     - `Blank`: Cho phép để trống
     - `Null`: Cho phép NULL trong database

### Bước 4: Preview hoặc Generate

- Click **"Preview"** để xem trước các files sẽ được tạo
- Click **"Generate & Download"** để tải về project dạng ZIP

### Bước 5: Sử dụng Project đã tạo

```bash
# Giải nén file
unzip your_project.zip
cd your_project

# Cài đặt dependencies
pip install -r requirements.txt

# Chạy migrations
python manage.py makemigrations
python manage.py migrate

# Tạo superuser (optional)
python manage.py createsuperuser

# Chạy development server
python manage.py runserver
```

Truy cập:
- API: http://localhost:8000/api/
- Admin: http://localhost:8000/admin/
- Health check: http://localhost:8000/api/health/

## 📁 Cấu trúc Project được sinh ra

```
your_project/
├── manage.py                    # Django management script
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Docker configuration
├── .gitignore                   # Git ignore rules
├── README.md                    # Project documentation
├── .github/
│   └── workflows/
│       └── ci-cd.yml           # CI/CD pipeline
├── django_api/                  # Main project folder
│   ├── __init__.py
│   ├── settings.py             # Django settings
│   ├── urls.py                 # Main URL configuration
│   └── wsgi.py                 # WSGI application
└── api/                         # Django app
    ├── __init__.py
    ├── apps.py                 # App configuration
    ├── models.py               # Database models
    ├── serializers.py          # DRF serializers
    ├── views.py                # API views
    ├── urls.py                 # App URL configuration
    └── migrations/
        └── __init__.py
```

## 🎯 Ví dụ sử dụng

### Ví dụ 1: E-commerce API

**Models:**
1. **Product**
   - name: CharField (max_length=200)
   - description: TextField
   - price: DecimalField (max_digits=10, decimal_places=2)
   - stock: IntegerField
   - is_active: BooleanField

2. **Category**
   - name: CharField (max_length=100)
   - slug: SlugField
   - description: TextField (blank=True)

### Ví dụ 2: Blog API

**Models:**
1. **Post**
   - title: CharField (max_length=200)
   - content: TextField
   - slug: SlugField
   - published_date: DateTimeField
   - is_published: BooleanField

2. **Comment**
   - author: CharField (max_length=100)
   - email: EmailField
   - content: TextField
   - created_at: DateTimeField

## 🔧 API Endpoints được tạo

Với mỗi model, Dev Portal tự động tạo các endpoints:

- `GET /api/{endpoint}/` - List all objects
- `POST /api/{endpoint}/` - Create new object
- `GET /api/{endpoint}/{id}/` - Get single object
- `PUT /api/{endpoint}/{id}/` - Update object
- `DELETE /api/{endpoint}/{id}/` - Delete object
- `GET /api/health/` - Health check

## 🐳 Docker Support

Project được tạo sẽ có Dockerfile sẵn sàng:

```bash
# Build image
docker build -t your_project .

# Run container
docker run -p 8000:8000 your_project

# Run with docker-compose
docker-compose up -d
```

## 🔄 CI/CD Pipeline

Nếu enable CI/CD, project sẽ có GitHub Actions workflow tự động:

1. **Test** - Chạy tests và validation
2. **Build & Push** - Build Docker image và push lên registry
3. **Update Manifests** - Tự động update k8s manifests trong Repository_B
4. **ArgoCD Sync** - Trigger ArgoCD để deploy

### Setup CI/CD:

1. Tạo Personal Access Token (PAT) trên GitHub
2. Thêm secret `PAT_TOKEN` vào repository settings
3. Push code lên GitHub
4. CI/CD sẽ tự động chạy

## 🎨 Customization

Project được tạo có thể customize dễ dàng:

- **Thêm models mới**: Chỉnh sửa `models.py`
- **Custom views**: Chỉnh sửa `views.py`
- **Thêm authentication**: Update `settings.py` và add middleware
- **Thay đổi database**: Update `DATABASES` trong `settings.py`
- **Add permissions**: Implement trong views hoặc serializers

## 📚 Tech Stack

**Dev Portal:**
- FastAPI - Backend framework
- Pydantic - Data validation
- Uvicorn - ASGI server
- HTML/CSS/JS - Frontend
- Tailwind CSS - UI styling
- SweetAlert2 - Beautiful alerts

**Generated Project:**
- Django 4.2.7
- Django REST Framework 3.14.0
- Django CORS Headers 4.3.1
- Gunicorn 21.2.0
- Python 3.11

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

MIT License - feel free to use this project for any purpose!

## 💡 Tips

1. **Model naming**: Sử dụng singular form (Product, không phải Products)
2. **Endpoint naming**: Sử dụng plural form (products, không phải product)
3. **Field naming**: Sử dụng snake_case (created_at, không phải createdAt)
4. **Always add timestamp fields**: created_at và updated_at (tự động thêm)
5. **Preview trước khi generate**: Kiểm tra code trước khi download

## 🐛 Troubleshooting

### Port đã được sử dụng
```bash
# Thay đổi port
python main.py --port 8081
# hoặc
uvicorn main:app --host 0.0.0.0 --port 8081
```

### Lỗi khi generate project
- Kiểm tra tên project và app name không chứa ký tự đặc biệt
- Đảm bảo có ít nhất 1 model và 1 field
- Kiểm tra field types và parameters

### Project không chạy được
```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Check Django installation
python -c "import django; print(django.get_version())"

# Run migrations
python manage.py migrate
```

## 📞 Support

Nếu có vấn đề hoặc câu hỏi, vui lòng:
1. Check documentation này
2. Xem examples trong repository
3. Create an issue trên GitHub

---

**Happy Coding!** 🚀

Made with ❤️ by Django Dev Portal Team

