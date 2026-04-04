# 💰 Moneytodo – Family Expense Manager

Ứng dụng quản lý thu chi hàng ngày cho gia đình, xây dựng bằng Python + Tkinter + SQLite.

## Tính năng

- **Thu Chi Hàng Ngày**: Thêm/sửa/xóa các khoản thu chi với danh mục, danh mục con, diễn giải, lọc theo tháng, sắp xếp A-Z/0-9
- **Xuất Excel**: Báo cáo tháng đẹp định dạng (tóm tắt + chi tiết giao dịch)
- **Quản Lý Danh Mục**: Tạo/sửa/xóa danh mục chính và danh mục con
- **Dự Chi Cố Định**: Nhập các khoản chi cố định hàng tháng, tick khi đã dành đủ tiền
- **Ghi Chú & Nhắc Nhở**: Nhập công việc + ngày, popup nhắc nhở desktop 1 lần vào đúng ngày

## Cài đặt

```bash
pip install -r requirements.txt
python main.py
```

## Yêu cầu

- Python 3.8+
- tkinter (thường có sẵn; nếu thiếu: `sudo apt install python3-tk`)
- openpyxl (xuất Excel)

## Stack

| Thành phần | Công nghệ |
|-----------|-----------|
| GUI       | Tkinter   |
| Database  | SQLite3   |
| Excel     | openpyxl  |

## Cấu trúc dự án

```
Moneytodo/
├── main.py              # Khởi động app
├── database.py          # SQLite CRUD
├── requirements.txt
├── ui/
│   ├── expenses_tab.py  # Thu chi hàng ngày
│   ├── categories_tab.py# Quản lý danh mục
│   ├── planned_tab.py   # Dự chi cố định
│   └── reminders_tab.py # Ghi chú & nhắc nhở
└── utils/
    └── excel_export.py  # Xuất báo cáo Excel
```