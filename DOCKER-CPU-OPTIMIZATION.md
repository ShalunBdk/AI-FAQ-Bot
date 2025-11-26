# 🚀 CPU Optimization для Docker Build

## Проблема

При сборке Docker образа скачивались NVIDIA CUDA пакеты (~1.5 ГБ):
- `nvidia_cublas_cu12` (594 MB)
- `nvidia_cudnn_cu12` (706 MB)
- `nvidia_cuda_nvrtc_cu12` (88 MB)
- и другие...

**Причина:** PyTorch по умолчанию устанавливает CUDA-версию, хотя обработка происходит на CPU.

---

## ✅ Решение

Dockerfile теперь **автоматически** устанавливает CPU-only версию PyTorch, что:
- ⚡ Ускоряет сборку образа на 5-10 минут
- 💾 Экономит ~1.5 ГБ дискового пространства
- 🎯 Не требует изменений в коде

### Что было изменено

#### 1. `docker/Dockerfile` (строки 18-24)

```dockerfile
# ВАЖНО: Сначала устанавливаем PyTorch CPU-only (без CUDA)
# Это экономит ~1.5 ГБ и ускоряет сборку
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Затем устанавливаем остальные зависимости
# sentence-transformers будет использовать уже установленный CPU PyTorch
RUN pip install --no-cache-dir -r requirements.txt
```

#### 2. `requirements.txt`

Убрана явная зависимость `torch>=2.6.0`, так как она устанавливается отдельно в Dockerfile.

---

## 📦 Локальная разработка (без Docker)

Для локальной разработки на CPU используйте:

```bash
# 1. Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# 2. Установите CPU-only версию PyTorch
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 3. Установите остальные зависимости
pip install -r requirements.txt
```

### Альтернатива: используйте `requirements-cpu.txt`

```bash
# Сначала установите PyTorch CPU-only
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Затем остальные зависимости
pip install -r requirements-cpu.txt
```

---

## 🔍 Проверка установленной версии

После установки проверьте, что используется CPU-only версия:

```python
import torch
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")  # Должно быть False
print(f"CPU device: {torch.device('cpu')}")
```

Ожидаемый вывод:
```
PyTorch version: 2.x.x+cpu
CUDA available: False
CPU device: cpu
```

---

## 📊 Сравнение размеров образов

| Версия | Размер образа | Время сборки* |
|--------|--------------|--------------|
| **С CUDA** (старая) | ~3.5 GB | ~15 мин |
| **CPU-only** (новая) | ~2.0 GB | ~7 мин |
| **Экономия** | **1.5 GB** | **~8 мин** |

*При скорости интернета ~20 Мбит/с

---

## ⚠️ Когда НЕ использовать CPU-only

Если у вас есть GPU (NVIDIA) и вы хотите ускорить обработку запросов:

1. **Откатите изменения в Dockerfile:**
   ```dockerfile
   # Закомментируйте строки с CPU-only установкой
   # RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

   # Установите обычную версию
   RUN pip install --no-cache-dir -r requirements.txt
   ```

2. **Верните `torch>=2.6.0` в `requirements.txt`**

3. **Добавьте GPU support в docker-compose.yml:**
   ```yaml
   services:
     web-admin:
       deploy:
         resources:
           reservations:
             devices:
               - driver: nvidia
                 count: 1
                 capabilities: [gpu]
   ```

---

## 📝 История изменений

**2025-01-26** - Добавлена CPU-only оптимизация:
- Dockerfile обновлён для использования CPU PyTorch
- Создан `requirements-cpu.txt` для локальной разработки
- Экономия ~1.5 ГБ и 8 минут при сборке

---

## 🔗 Полезные ссылки

- [PyTorch CPU installation](https://pytorch.org/get-started/locally/)
- [Dockerfile best practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [sentence-transformers без GPU](https://www.sbert.net/docs/installation.html)
