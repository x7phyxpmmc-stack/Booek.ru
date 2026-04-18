// ============================================================================
// MEDIA TRACKER - JAVASCRIPT FUNCTIONS
// ============================================================================

// Функция для подтверждения удаления категории
function deleteCategory(categoryId) {
    if (confirm('Вы уверены? Будут удалены все записи в этой категории.')) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/category/${categoryId}/delete`;
        document.body.appendChild(form);
        form.submit();
    }
}

// Функция для подтверждения удаления элемента
function deleteItem(itemId) {
    if (confirm('Вы уверены? Эта операция не может быть отменена.')) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/item/${itemId}/delete`;
        document.body.appendChild(form);
        form.submit();
    }
}

// Предпросмотр загруженного изображения
document.addEventListener('DOMContentLoaded', function() {
    const coverInput = document.getElementById('cover_image');
    
    if (coverInput) {
        coverInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            
            if (file) {
                // Проверяем размер файла (максимум 16MB)
                const maxSize = 16 * 1024 * 1024;
                if (file.size > maxSize) {
                    alert('Файл слишком большой. Максимум: 16MB');
                    coverInput.value = '';
                    return;
                }
                
                // Проверяем тип файла
                const allowedTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];
                if (!allowedTypes.includes(file.type)) {
                    alert('Неподдерживаемый формат. Разрешены: PNG, JPG, GIF, WebP');
                    coverInput.value = '';
                    return;
                }
                
                // Предпросмотр
                const reader = new FileReader();
                reader.onload = function(event) {
                    // Здесь можно добавить предпросмотр если нужно
                    console.log('Файл выбран:', file.name);
                };
                reader.readAsDataURL(file);
            }
        });
    }
});

// Анимация загрузки страницы
window.addEventListener('load', function() {
    document.body.style.animation = 'fadeIn 0.3s ease';
});

@keyframes fadeIn {
    from {
        opacity: 0;
    }
    to {
        opacity: 1;
    }
}

// Улучшенная валидация формы перед отправкой
const forms = document.querySelectorAll('form');
forms.forEach(form => {
    form.addEventListener('submit', function(e) {
        // Проверяем, есть ли обязательные поля
        const requiredFields = this.querySelectorAll('input[required], textarea[required], select[required]');
        let isValid = true;
        
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                field.style.borderColor = '#EF4444';
                isValid = false;
            } else {
                field.style.borderColor = '';
            }
        });
        
        if (!isValid) {
            e.preventDefault();
            alert('Пожалуйста, заполните все обязательные поля');
        }
    });
    
    // Убираем красную границу при вводе
    const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
    inputs.forEach(input => {
        input.addEventListener('input', function() {
            if (this.value.trim()) {
                this.style.borderColor = '';
            }
        });
    });
});

// Поддержка темного режима (если система использует)
if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.documentElement.style.colorScheme = 'dark';
}

// Слушаем изменение темы
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    document.documentElement.style.colorScheme = e.matches ? 'dark' : 'light';
});

// Добавляем класс 'loaded' к body когда страница загрузилась
window.addEventListener('load', function() {
    document.body.classList.add('loaded');
});

// Для улучшения производительности - ленивая загрузка изображений
if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                imageObserver.unobserve(img);
            }
        });
    });
    
    document.querySelectorAll('img[data-src]').forEach(img => imageObserver.observe(img));
}
