import sys
import json
import os
from datetime import datetime
from collections import defaultdict

import fitz  # PyMuPDF
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QBrush,
    QFont, QTransform, QCursor
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QFileDialog,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem,
    QToolBar, QVBoxLayout, QWidget, QHBoxLayout, QPushButton,
    QColorDialog, QInputDialog, QMessageBox
)


class PDFGraphicsView(QGraphicsView):
    """自定义 QGraphicsView，支持缩放和拖拽"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)  # 默认左键拖拽移动
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def wheelEvent(self, event):
        """滚轮缩放"""
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            factor = zoom_in_factor
        else:
            factor = zoom_out_factor
        self.scale(factor, factor)


class AnnotationItem(QGraphicsRectItem):
    """可交互的批注图形项，基类"""
    def __init__(self, rect, annotation_data, scene):
        super().__init__(rect)
        self.annotation_data = annotation_data  # 存储原始数据
        self.scene_ref = scene
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            # 当批注被移动时，更新 annotation_data 中的矩形坐标
            new_pos = value
            old_rect = self.rect()
            new_rect = QRectF(new_pos.x(), new_pos.y(), old_rect.width(), old_rect.height())
            self.annotation_data['rect'] = [
                new_rect.x(), new_rect.y(),
                new_rect.width(), new_rect.height()
            ]
            self.scene_ref.parent().annotations_changed.emit()
        return super().itemChange(change, value)


class HighlightAnnotation(AnnotationItem):
    """高亮批注"""
    def __init__(self, rect, color, annotation_data, scene):
        super().__init__(rect, annotation_data, scene)
        self.setPen(QPen(Qt.NoPen))
        self.setBrush(QBrush(QColor(color)))
        self.setOpacity(0.3)


class RectangleAnnotation(AnnotationItem):
    """矩形框批注"""
    def __init__(self, rect, color, annotation_data, scene):
        super().__init__(rect, annotation_data, scene)
        self.setPen(QPen(QColor(color), 2))
        self.setBrush(QBrush(Qt.NoBrush))


class TextAnnotation(QGraphicsTextItem):
    """文本批注"""
    def __init__(self, text, pos, color, annotation_data, scene):
        super().__init__(text)
        self.annotation_data = annotation_data
        self.scene_ref = scene
        self.setDefaultTextColor(QColor(color))
        self.setPos(pos)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            new_pos = value
            self.annotation_data['pos'] = [new_pos.x(), new_pos.y()]
            self.scene_ref.parent().annotations_changed.emit()
        return super().itemChange(change, value)


class PDFGraphicsScene(QGraphicsScene):
    """场景，管理 PDF 页面图像和批注项"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdf_item = None
        self.current_page_index = 0
        self.page_rect = QRectF()
        self.annotations = []  # 存储所有批注项
        self.current_tool = None  # 'highlight', 'rectangle', 'text', 'select'
        self.current_color = "#FFFF00"  # 默认黄色
        self.start_point = None  # 用于右键拖拽创建临时批注
        self.temp_item = None

    def set_pdf_page(self, pixmap, page_index, page_rect):
        """设置当前显示的 PDF 页面"""
        self.clear()
        self.pdf_item = QGraphicsPixmapItem(pixmap)
        # 让页面图像不拦截鼠标事件，以便批注项可以接收到
        self.pdf_item.setAcceptedMouseButtons(Qt.NoButton)
        self.pdf_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.addItem(self.pdf_item)
        self.current_page_index = page_index
        self.page_rect = page_rect
        # 重新加载该页的批注
        self.load_page_annotations()

    def load_page_annotations(self):
        """从父窗口的 annotation_manager 加载当前页的批注"""
        manager = self.parent().annotation_manager
        page_annos = manager.get_annotations_for_page(self.current_page_index)
        for anno in page_annos:
            self.add_annotation_item(anno)

    def add_annotation_item(self, anno_data):
        """根据数据创建图形项并添加到场景"""
        anno_type = anno_data['type']
        color = anno_data.get('color', '#FFFF00')
        if anno_type in ('highlight', 'rectangle'):
            rect_data = anno_data['rect']
            rect = QRectF(rect_data[0], rect_data[1], rect_data[2], rect_data[3])
            if anno_type == 'highlight':
                item = HighlightAnnotation(rect, color, anno_data, self)
            else:
                item = RectangleAnnotation(rect, color, anno_data, self)
            self.addItem(item)
            self.annotations.append(item)
        elif anno_type == 'text':
            pos_data = anno_data['pos']
            pos = QPointF(pos_data[0], pos_data[1])
            text = anno_data.get('content', '')
            item = TextAnnotation(text, pos, color, anno_data, self)
            self.addItem(item)
            self.annotations.append(item)

    def remove_annotation_item(self, item):
        """从场景中移除批注项，并从列表中删除"""
        if item in self.annotations:
            self.annotations.remove(item)
            self.removeItem(item)

    def mousePressEvent(self, event):
        """处理鼠标按下：右键开始绘制临时批注（除非当前工具为 select）"""
        if event.button() == Qt.RightButton and self.current_tool and self.current_tool != 'select':
            self.start_point = event.scenePos()
            if self.current_tool == 'text':
                # 文本批注：点击位置弹出输入框
                text, ok = QInputDialog.getText(self.parent(), "文本批注", "输入文本:")
                if ok and text:
                    self.create_text_annotation(self.start_point, text)
                self.start_point = None
                return
            else:
                # 高亮或矩形：创建临时矩形
                self.temp_item = QGraphicsRectItem(QRectF(self.start_point, self.start_point))
                self.temp_item.setPen(QPen(Qt.red, 1, Qt.DashLine))
                self.addItem(self.temp_item)
        else:
            # 其他情况（包括左键）交给基类处理（例如选择）
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动时更新临时矩形（仅当右键拖拽且存在临时项）"""
        if self.temp_item and self.start_point:
            rect = QRectF(self.start_point, event.scenePos()).normalized()
            self.temp_item.setRect(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放：完成临时批注创建（右键）"""
        if event.button() == Qt.RightButton and self.temp_item:
            rect = self.temp_item.rect()
            self.removeItem(self.temp_item)
            self.temp_item = None
            if rect.width() > 5 and rect.height() > 5:
                self.create_annotation(rect)
        else:
            super().mouseReleaseEvent(event)

    def create_annotation(self, rect):
        """根据当前工具创建批注"""
        if self.current_tool == 'highlight':
            anno_type = 'highlight'
        elif self.current_tool == 'rectangle':
            anno_type = 'rectangle'
        else:
            return

        # 创建数据对象
        anno_data = {
            'page': self.current_page_index,
            'type': anno_type,
            'rect': [rect.x(), rect.y(), rect.width(), rect.height()],
            'color': self.current_color,
            'created': datetime.now().isoformat(),
            'content': ''
        }
        # 添加到管理器和场景
        self.parent().annotation_manager.add_annotation(anno_data)
        self.add_annotation_item(anno_data)
        self.parent().annotations_changed.emit()

    def create_text_annotation(self, pos, text):
        """创建文本批注"""
        anno_data = {
            'page': self.current_page_index,
            'type': 'text',
            'pos': [pos.x(), pos.y()],
            'color': self.current_color,
            'created': datetime.now().isoformat(),
            'content': text
        }
        self.parent().annotation_manager.add_annotation(anno_data)
        self.add_annotation_item(anno_data)
        self.parent().annotations_changed.emit()


class AnnotationManager:
    """管理所有批注数据的加载、保存、查询"""
    def __init__(self, pdf_path=None):
        self.pdf_path = pdf_path
        self.annotations = []  # 所有批注数据列表
        self.anno_file_path = None
        if pdf_path:
            self.anno_file_path = pdf_path + '.anno'
            self.load_from_file()

    def set_pdf_path(self, pdf_path):
        self.pdf_path = pdf_path
        self.anno_file_path = pdf_path + '.anno'
        self.load_from_file()

    def load_from_file(self, file_path=None):
        """从 JSON 文件加载批注"""
        path = file_path or self.anno_file_path
        if path and os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.annotations = json.load(f)
            except:
                self.annotations = []
        else:
            self.annotations = []

    def save_to_file(self, file_path=None):
        """保存批注到 JSON 文件"""
        path = file_path or self.anno_file_path
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.annotations, f, indent=2, ensure_ascii=False)

    def get_annotations_for_page(self, page_index):
        """返回指定页的批注列表"""
        return [a for a in self.annotations if a.get('page') == page_index]

    def add_annotation(self, anno_data):
        """添加一条批注数据"""
        self.annotations.append(anno_data)

    def remove_annotation(self, anno_data):
        """删除一条批注数据（根据内容完全匹配）"""
        try:
            self.annotations.remove(anno_data)
        except ValueError:
            pass

    def clear(self):
        self.annotations = []

    def merge_from(self, other_manager):
        """合并另一个管理器的批注（简单追加，可去重）"""
        self.annotations.extend(other_manager.annotations)


class MainWindow(QMainWindow):
    """主窗口"""
    annotations_changed = pyqtSignal()  # 批注变更信号，用于触发自动保存

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF 批注工具")
        self.resize(900, 700)

        # 初始化变量
        self.pdf_document = None
        self.current_page = 0
        self.annotation_manager = AnnotationManager()
        self.auto_save_timer = None

        # 创建中心控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 创建工具栏
        self.create_toolbar()

        # 创建图形视图和场景
        self.scene = PDFGraphicsScene(self)
        self.view = PDFGraphicsView(self)
        self.view.setScene(self.scene)
        layout.addWidget(self.view)

        # 状态栏
        self.statusBar().showMessage("就绪")

        # 连接信号
        self.annotations_changed.connect(self.on_annotations_changed)

        # 创建菜单栏
        menubar = self.menuBar()
        help_menu = menubar.addMenu("帮助")
        help_action = QAction("使用说明", self)
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)

    def create_toolbar(self):
        """创建工具栏和菜单"""
        toolbar = QToolBar("工具")
        self.addToolBar(toolbar)

        # 文件操作
        open_action = QAction("打开 PDF", self)
        open_action.triggered.connect(self.open_pdf)
        toolbar.addAction(open_action)

        export_action = QAction("导出批注", self)
        export_action.triggered.connect(self.export_annotations)
        toolbar.addAction(export_action)

        import_action = QAction("导入批注", self)
        import_action.triggered.connect(self.import_annotations)
        toolbar.addAction(import_action)

        write_pdf_action = QAction("写入 PDF", self)
        write_pdf_action.triggered.connect(self.write_annotations_to_pdf)
        toolbar.addAction(write_pdf_action)

        toolbar.addSeparator()

        # 工具选择（高亮、矩形、文本）
        self.highlight_btn = QAction("高亮", self)
        self.highlight_btn.setCheckable(True)
        self.highlight_btn.triggered.connect(lambda: self.set_tool('highlight'))
        toolbar.addAction(self.highlight_btn)

        self.rect_btn = QAction("矩形", self)
        self.rect_btn.setCheckable(True)
        self.rect_btn.triggered.connect(lambda: self.set_tool('rectangle'))
        toolbar.addAction(self.rect_btn)

        self.text_btn = QAction("文本", self)
        self.text_btn.setCheckable(True)
        self.text_btn.triggered.connect(lambda: self.set_tool('text'))
        toolbar.addAction(self.text_btn)

        toolbar.addSeparator()

        # 选择模式按钮
        self.select_btn = QAction("选择", self)
        self.select_btn.setCheckable(True)
        self.select_btn.triggered.connect(self.toggle_select_mode)
        toolbar.addAction(self.select_btn)

        # 颜色选择
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(24, 24)
        self.color_btn.setStyleSheet("background-color: #FFFF00;")
        self.color_btn.clicked.connect(self.choose_color)
        toolbar.addWidget(self.color_btn)

        # 页面导航
        self.prev_btn = QAction("上一页", self)
        self.prev_btn.triggered.connect(self.prev_page)
        toolbar.addAction(self.prev_btn)

        self.page_label = QAction("第 1 页", self)
        toolbar.addAction(self.page_label)

        self.next_btn = QAction("下一页", self)
        self.next_btn.triggered.connect(self.next_page)
        toolbar.addAction(self.next_btn)

        # 跳转到指定页码
        self.jump_btn = QAction("跳转", self)
        self.jump_btn.triggered.connect(self.jump_to_page)
        toolbar.addAction(self.jump_btn)

        toolbar.addSeparator()

        # 删除选中批注
        self.delete_btn = QAction("删除", self)
        self.delete_btn.triggered.connect(self.delete_selected_annotations)
        toolbar.addAction(self.delete_btn)

    def keyPressEvent(self, event):
        """处理键盘事件：按下 Delete 键删除选中批注"""
        if event.key() == Qt.Key_Delete:
            self.delete_selected_annotations()
        else:
            super().keyPressEvent(event)

    def toggle_select_mode(self, checked):
        """切换选择模式：选中时视图不可拖拽，左键用于选择项；取消时恢复拖拽"""
        if checked:
            self.view.setDragMode(QGraphicsView.NoDrag)
            self.set_tool('select')
            # 取消其他工具的选中状态
            self.highlight_btn.setChecked(False)
            self.rect_btn.setChecked(False)
            self.text_btn.setChecked(False)
        else:
            self.view.setDragMode(QGraphicsView.ScrollHandDrag)
            # 退出选择模式，将工具设为 None 或保留上一个工具？
            self.scene.current_tool = None

    def set_tool(self, tool_name):
        """设置当前批注工具（高亮/矩形/文本）"""
        self.scene.current_tool = tool_name
        # 如果当前是选择模式，则退出选择模式
        if self.select_btn.isChecked():
            self.select_btn.setChecked(False)
            self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        # 更新按钮状态
        self.highlight_btn.setChecked(tool_name == 'highlight')
        self.rect_btn.setChecked(tool_name == 'rectangle')
        self.text_btn.setChecked(tool_name == 'text')

    def delete_selected_annotations(self):
        """删除当前选中的所有批注"""
        selected_items = self.scene.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            if hasattr(item, 'annotation_data'):
                self.annotation_manager.remove_annotation(item.annotation_data)
                self.scene.remove_annotation_item(item)

        self.annotations_changed.emit()
        self.statusBar().showMessage(f"已删除 {len(selected_items)} 个批注", 2000)

    def choose_color(self):
        """选择批注颜色"""
        color = QColorDialog.getColor(QColor(self.scene.current_color), self)
        if color.isValid():
            self.scene.current_color = color.name()
            self.color_btn.setStyleSheet(f"background-color: {color.name()};")

    def open_pdf(self):
        """打开 PDF 文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开 PDF", "", "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        try:
            self.pdf_document = fitz.open(file_path)
            self.annotation_manager.set_pdf_path(file_path)
            self.current_page = 0
            self.load_page(self.current_page)
            self.statusBar().showMessage(f"已打开: {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开 PDF: {str(e)}")

    def load_page(self, page_index):
        """加载指定页面到场景"""
        if not self.pdf_document:
            return
        page = self.pdf_document[page_index]
        zoom = 2.0  # 初始缩放系数，可根据需要调整
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        # 转换为 QImage
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        qpix = QPixmap.fromImage(img)

        # 页面实际尺寸（点）用于坐标转换
        page_rect = page.rect  # fitz.Rect
        self.scene.set_pdf_page(qpix, page_index, QRectF(page_rect.x0, page_rect.y0,
                                                         page_rect.width, page_rect.height))
        self.view.setScene(self.scene)
        # 更新页面标签
        self.page_label.setText(f"第 {page_index+1} 页")
        # 居中显示（通过设置场景中心）
        self.view.centerOn(qpix.width()/2, qpix.height()/2)

    def prev_page(self):
        if self.pdf_document and self.current_page > 0:
            self.current_page -= 1
            self.load_page(self.current_page)

    def next_page(self):
        if self.pdf_document and self.current_page < len(self.pdf_document) - 1:
            self.current_page += 1
            self.load_page(self.current_page)

    def jump_to_page(self):
        """跳转到指定页码"""
        if not self.pdf_document:
            QMessageBox.information(self, "提示", "请先打开 PDF 文件")
            return
        total_pages = len(self.pdf_document)
        current = self.current_page + 1
        page_str, ok = QInputDialog.getText(
            self, "跳转到页码",
            f"输入页码 (1-{total_pages}):",
            text=str(current)
        )
        if ok and page_str:
            try:
                page = int(page_str)
                if 1 <= page <= total_pages:
                    self.current_page = page - 1
                    self.load_page(self.current_page)
                else:
                    QMessageBox.warning(self, "错误", f"页码必须在 1 到 {total_pages} 之间")
            except ValueError:
                QMessageBox.warning(self, "错误", "请输入有效的数字")

    def show_help(self):
        """显示使用说明"""
        help_text = """
        PDF 批注工具使用说明

        鼠标操作:
        - 左键拖拽: 移动页面（默认模式）
        - 滚轮: 缩放页面
        - 右键拖拽: 创建批注（需先选择高亮/矩形/文本工具）

        批注工具:
        - 点击“高亮”/“矩形”/“文本”按钮后，使用鼠标右键在页面上拖拽创建对应批注。
        - 文本工具：右键点击页面位置，输入文本即可创建文本批注。
        - 可通过颜色按钮选择批注颜色。

        选择与删除:
        - 点击“选择”按钮进入选择模式（左键用于选中批注，支持Ctrl多选）。
        - 选中批注后，点击工具栏“删除”按钮或按 Delete 键即可删除。
        - 再次点击“选择”按钮退出选择模式，恢复左键移动页面。

        页面导航:
        - 上一页/下一页按钮切换页面
        - 跳转按钮可输入页码跳转

        批注自动保存到同目录下的 .anno 文件。
        导出/导入功能可迁移批注数据。
        写入 PDF 可将批注作为标准注释另存为新 PDF。
        """
        QMessageBox.information(self, "使用说明", help_text)

    def on_annotations_changed(self):
        """批注发生变更时调用自动保存"""
        if self.annotation_manager.pdf_path:
            self.annotation_manager.save_to_file()
            self.statusBar().showMessage("批注已自动保存", 2000)

    def export_annotations(self):
        """导出批注到指定的 JSON 文件"""
        if not self.annotation_manager.annotations:
            QMessageBox.information(self, "提示", "没有批注可导出")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出批注", "", "JSON Files (*.json)"
        )
        if file_path:
            self.annotation_manager.save_to_file(file_path)
            self.statusBar().showMessage(f"批注已导出到 {file_path}")

    def import_annotations(self):
        """从 JSON 文件导入批注并合并到当前文档"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入批注", "", "JSON Files (*.json)"
        )
        if not file_path:
            return
        try:
            # 临时加载外部批注
            temp_manager = AnnotationManager()
            temp_manager.load_from_file(file_path)
            if not temp_manager.annotations:
                QMessageBox.information(self, "提示", "文件中没有批注")
                return
            # 合并
            self.annotation_manager.merge_from(temp_manager)
            # 重新加载当前页以显示新批注
            self.load_page(self.current_page)
            self.annotations_changed.emit()
            self.statusBar().showMessage("批注导入完成")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败: {str(e)}")

    def write_annotations_to_pdf(self):
        """将当前批注写入 PDF（生成新文件）"""
        if not self.pdf_document:
            return
        if not self.annotation_manager.annotations:
            QMessageBox.information(self, "提示", "没有批注可写入")
            return

        # 选择保存路径
        default_name = os.path.splitext(self.annotation_manager.pdf_path)[0] + "_annotated.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存带批注的 PDF", default_name, "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        try:
            # 复制原文档（避免修改原文件）
            new_doc = fitz.open(self.annotation_manager.pdf_path)

            # 按页面分组批注
            page_annos = defaultdict(list)
            for anno in self.annotation_manager.annotations:
                page_annos[anno['page']].append(anno)

            # 为每一页添加注释
            for page_idx, annos in page_annos.items():
                if page_idx >= len(new_doc):
                    continue
                page = new_doc[page_idx]
                for anno in annos:
                    anno_type = anno['type']
                    color = anno.get('color', '#ffff00')
                    # 转换为fitz颜色（0-1 float）
                    c = QColor(color)
                    fitz_color = (c.redF(), c.greenF(), c.blueF())

                    if anno_type == 'highlight':
                        # 高亮矩形
                        rect_data = anno['rect']
                        rect = fitz.Rect(rect_data)
                        page.add_highlight_annot(rect)
                    elif anno_type == 'rectangle':
                        rect_data = anno['rect']
                        rect = fitz.Rect(rect_data)
                        annot = page.add_rect_annot(rect)
                        annot.set_colors(stroke=fitz_color)
                        annot.update()
                    elif anno_type == 'text':
                        pos_data = anno['pos']
                        pos = fitz.Point(pos_data)
                        content = anno.get('content', '')
                        annot = page.add_text_annot(pos, content)
                        annot.set_colors(stroke=fitz_color)
                        annot.update()
            # 保存新文档
            new_doc.save(file_path, garbage=4, deflate=True)
            new_doc.close()
            self.statusBar().showMessage(f"已保存带批注的 PDF: {file_path}")
            QMessageBox.information(self, "完成", f"批注已写入 PDF，保存为:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"写入 PDF 失败: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())