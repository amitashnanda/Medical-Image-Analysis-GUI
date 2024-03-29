import sys
import cv2

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsView, QGraphicsScene, QAction, QFileDialog, QGraphicsItem,
    QButtonGroup, QRadioButton, QGraphicsPixmapItem, QGridLayout, QSizePolicy, QMenu, 
)
from PyQt5.QtGui import QPixmap, QPen, QColor, QPainter, QPainterPath, QImage
from PyQt5.QtCore import Qt, QPointF, QRectF, QSizeF, pyqtSignal
from enum import Enum

class AnnotationType(Enum):
    NONE = 0
    FREEHAND = 1
    SQUARE = 2
    CIRCLE = 3
    RECTANGLE = 4
    TRIANGLE = 5
    ELLIPSE = 6

class AnnotationItem(QGraphicsItem):
    removed = pyqtSignal(QGraphicsItem)

    def __init__(self, path, pen):
        super().__init__()
        self.path = path if path is not None else QPainterPath()
        self.pen = pen

    def boundingRect(self):
        return self.path.boundingRect()

    def paint(self, painter, option, widget):
        painter.setPen(self.pen)
        painter.drawPath(self.path)

    def removeFromScene(self):
        if self.scene():
            self.scene().removeItem(self)
            self.removed.emit(self)

class AnnotationView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.annotation_type = AnnotationType.NONE
        self.annotation_color = QColor("red")
        self.annotation_items = []
        self.drawn_paths = []
        self.current_item = None
        self.current_path = None
        self.setBackgroundBrush(Qt.black)
        self.panning = False
        self.last_mouse_position = QPointF()
        self.grabGesture(Qt.PinchGesture)

        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def set_annotation_type(self, annotation_type):
        self.annotation_type = annotation_type

    def mousePressEvent(self, event):
        if self.annotation_type != AnnotationType.NONE:
            self.start_point = self.mapToScene(event.pos())
            self.current_item = None
            if self.annotation_type == AnnotationType.FREEHAND:
                self.current_path = QPainterPath()
                self.current_path.moveTo(self.start_point)

    def mouseMoveEvent(self, event):
        if self.annotation_type != AnnotationType.NONE and hasattr(self, 'start_point'):
            end_point = self.mapToScene(event.pos())
            if self.annotation_type == AnnotationType.FREEHAND:
                if self.current_path:
                    self.current_path.lineTo(end_point)
                    pen = QPen(self.annotation_color)
                    pen.setWidth(2)
                    self.current_item = AnnotationItem(self.current_path, pen)
                    self.scene().addItem(self.current_item)
            else:
                shape_draw_functions = {
                    AnnotationType.SQUARE: self.draw_square,
                    AnnotationType.CIRCLE: self.draw_circle,
                    AnnotationType.RECTANGLE: self.draw_rectangle,
                    AnnotationType.TRIANGLE: self.draw_triangle,
                    AnnotationType.ELLIPSE: self.draw_ellipse
                }
                if self.current_item:
                    self.scene().removeItem(self.current_item) 
                self.current_item = shape_draw_functions[self.annotation_type](self.start_point, end_point)
                if self.current_item:
                    self.scene().addItem(self.current_item)

    def mouseReleaseEvent(self, event):
        if self.current_item is not None and self.annotation_type != AnnotationType.NONE:
            end_point = self.mapToScene(event.pos())
            if self.annotation_type != AnnotationType.FREEHAND:
                shape_draw_functions = {
                    AnnotationType.SQUARE: self.draw_square,
                    AnnotationType.CIRCLE: self.draw_circle,
                    AnnotationType.RECTANGLE: self.draw_rectangle,
                    AnnotationType.TRIANGLE: self.draw_triangle,
                    AnnotationType.ELLIPSE: self.draw_ellipse
                }
                self.drawn_paths.append(self.current_item.path)  
                self.current_item = shape_draw_functions[self.annotation_type](self.start_point, end_point)
                if self.current_item:
                    self.scene().addItem(self.current_item)

            delattr(self, 'start_point')  
            self.current_path = None 
            self.current_item = None 

        super().mouseReleaseEvent(event)

    def event(self, event):
        if event.type() == QtCore.QEvent.Gesture:
            return self.gestureEvent(event)
        return super().event(event)

    def gestureEvent(self, event):
        pinch = event.gesture(Qt.PinchGesture)
        if pinch:
            self.handlePinch(pinch)
        return True

    def handlePinch(self, gesture):
        changeFlags = gesture.changeFlags()
        if changeFlags & QtWidgets.QPinchGesture.ScaleFactorChanged:
            scaleFactor = gesture.scaleFactor()
            scaleFactor = max(min(scaleFactor, 2.0), 0.5)
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            self.scale(scaleFactor, scaleFactor)

    def remove_annotation_item(self, item):
        if item in self.annotation_items:
            self.annotation_items.remove(item)

    def draw_square(self, start_point, end_point):
        top_left = QPointF(min(start_point.x(), end_point.x()), min(start_point.y(), end_point.y()))
        side_length = max(abs(end_point.x() - start_point.x()), abs(end_point.y() - start_point.y()))
        side_length = max(side_length, 20)

        path = QPainterPath()
        rect = QRectF(top_left, QSizeF(side_length, side_length))

        path.addRect(rect)  
        pen = QPen(self.annotation_color)
        pen.setWidth(2)
        annotation_item = AnnotationItem(path, pen)
        self.annotation_items.append(annotation_item)
        return annotation_item

    def draw_circle(self, start_point, end_point):
        ellipse = QRectF(start_point, end_point).normalized()
        center = ellipse.center()
        radius = QPointF(center.x() - ellipse.left(), center.y() - ellipse.top()).manhattanLength()
        circle_path = QPainterPath()
        circle_path.addEllipse(center, radius, radius)
        pen = QPen(self.annotation_color)
        pen.setWidth(2)
        annotation_item = AnnotationItem(circle_path, pen)
        self.annotation_items.append(annotation_item)  
        return annotation_item

    def draw_rectangle(self, start_point, end_point):
        width = abs(end_point.x() - start_point.x())
        height = abs(end_point.y() - start_point.y())
        width = max(width, 2)
        height = max(height, 2)

        path = QPainterPath()
        top_left = QPointF(min(start_point.x(), end_point.x()), min(start_point.y(), end_point.y()))
        rect = QRectF(top_left, QSizeF(width, height))

        path.addRect(rect)
        pen = QPen(self.annotation_color)
        pen.setWidth(2)
        annotation_item = AnnotationItem(path, pen)
        self.annotation_items.append(annotation_item)
        return annotation_item

    def draw_triangle(self, start_point, end_point):
        triangle = QPainterPath()
        triangle.moveTo(start_point)
        triangle.lineTo(QPointF(start_point.x(), end_point.y()))
        if end_point.y() < start_point.y():
            end_point.setY(start_point.y() + 1)
        triangle.lineTo(end_point)
        triangle.lineTo(start_point)
        pen = QPen(self.annotation_color)
        pen.setWidth(2)
        annotation_item = AnnotationItem(triangle, pen)
        self.annotation_items.append(annotation_item) 
        return annotation_item

    def draw_ellipse(self, start_point, end_point):
        width = abs(end_point.x() - start_point.x())
        height = abs(end_point.y() - start_point.y())
        width = max(width, 1)
        height = max(height, 1)
        top_left = QPointF(min(start_point.x(), end_point.x()), min(start_point.y(), end_point.y()))
        rect = QRectF(top_left, QSizeF(width, height))

        path = QPainterPath()
        path.addEllipse(rect) 

        pen = QPen(self.annotation_color)
        pen.setWidth(2)
        annotation_item = AnnotationItem(path, pen)
        self.annotation_items.append(annotation_item) 
        return annotation_item


class AnnotationMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.annotation_items = []
        self.drawn_paths = [] 
        self.setWindowTitle("Cancer Tissue Annotation")
        
        self.teal = "#254783"
        self.lightgrey = "#CFD9F5"
        self.darkgrey = "#E8E8E8"
        self.black = "#02040A"

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.central_widget.setStyleSheet("background-color: white;")

        self.layout = QGridLayout(self.central_widget)

        self.annotation_view = AnnotationView(self)
        self.layout.addWidget(self.annotation_view, 1, 0, 1, 1)
        self.is_fullscreen = False

        self.initial_zoom_factor = 0.35

        self.scene = QGraphicsScene(self)
        self.annotation_view.setScene(self.scene)
        
        self.image_label = QLabel()
        self.image_label.setStyleSheet("background-color: black;")

        self.header_container = QWidget()
        self.header_layout = QVBoxLayout(self.header_container)

        self.header_label = QLabel("Cancer Tissue Annotation")
        self.header_label.setStyleSheet(
            f"background-color: {self.teal};"
            "color: white;"
            "font-size: 50px;"
            "font-family: 'Arial', Times, serif;"
            "font-weight: bold;"
            "padding: 10px;"
            "border-radius: 10px;"
            "text-align: center;"
        )
        self.header_label.setAlignment(Qt.AlignCenter)

        self.header_layout.addWidget(self.header_label)

        self.layout.addWidget(self.header_container, 0, 0, 1, 2)

        self.scene.addWidget(self.image_label)

        self.header_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.tool_layout = QVBoxLayout()
        self.layout.addLayout(self.tool_layout, 1, 1, 1, 1)

        self.normalized_image_view = QGraphicsView()
        self.normalized_image_view.setStyleSheet("background-color: black;")
        self.normalized_image_scene = QGraphicsScene(self)
        self.normalized_image_view.setScene(self.normalized_image_scene)

        self.layout.setAlignment(Qt.AlignTop)

        button_height = 50
        button_width = 250

        self.annotation_options_label = QLabel("Image Options")
        self.annotation_options_label.setStyleSheet(
            "font-family: 'Times New Roman', serif;"  
            "font-size: 20px;"  
            f"color: {self.teal};"  
            f"background-color: {self.lightgrey};"  
            f"border: 2px solid {self.black};"  
            "border-radius: 5px;"  
            "padding: 10px;"  
        )
        self.annotation_options_label.setAlignment(Qt.AlignCenter)
        self.tool_layout.addWidget(self.annotation_options_label) 
        self.annotation_options_label.setFixedHeight(button_height)
        self.annotation_options_label.setFixedWidth(button_width)
        self.button_layout = QVBoxLayout()  

        self.fullscreen_button = QPushButton("Fullscreen")
        self.fullscreen_button.setStyleSheet(f"background-color: {self.teal}; color: white;")
        self.button_layout.addWidget(self.fullscreen_button)
        self.fullscreen_button.setFixedHeight(button_height)
        self.fullscreen_button.setFixedWidth(button_width)

        self.zoom_in_button = QPushButton("Zoom In")
        self.zoom_in_button.setStyleSheet(f"background-color: {self.teal}; color: white;")
        self.button_layout.addWidget(self.zoom_in_button)
        self.zoom_in_button.setFixedHeight(button_height)
        self.zoom_in_button.setFixedWidth(button_width)

        self.zoom_out_button = QPushButton("Zoom Out")
        self.zoom_out_button.setStyleSheet(f"background-color: {self.teal}; color: white;")
        self.button_layout.addWidget(self.zoom_out_button)
        self.zoom_out_button.setFixedHeight(button_height)
        self.zoom_out_button.setFixedWidth(button_width)

        self.download_button = QPushButton("Download")
        self.download_button.setStyleSheet(f"background-color: {self.teal}; color: white;")
        self.button_layout.addWidget(self.download_button)
        self.download_button.setFixedHeight(button_height)
        self.download_button.setFixedWidth(button_width)


        self.reset_button = QPushButton("Reset Image")
        self.reset_button.setStyleSheet(f"background-color: {self.teal}; color: white;")
        self.button_layout.addWidget(self.reset_button)
        self.reset_button.setFixedHeight(button_height)
        self.reset_button.setFixedWidth(button_width)

        self.original_pixmap = None


        self.tool_layout.addLayout(self.button_layout)

        self.annotation_button_group = QButtonGroup(self)

        self.annotation_button_layout = QVBoxLayout() 
        
        #Annotation options heading
        self.annotation_options_label = QLabel("Annotation Options")
        self.annotation_options_label.setStyleSheet(
            "font-family: 'Times New Roman', serif;"  
            "font-size: 20px;"  
            f"color: {self.teal};"  
            f"background-color: {self.lightgrey};"  
            "border: 2px solid #02040A;"  
            "border-radius: 5px;"  
            "padding: 10px;"  
        )
        self.annotation_options_label.setAlignment(Qt.AlignCenter)
        self.tool_layout.addWidget(self.annotation_options_label) 
        self.annotation_options_label.setFixedHeight(button_height)
        self.annotation_options_label.setFixedWidth(button_width)

        self.freehand_button = QRadioButton("Freehand")
        self.freehand_button.setStyleSheet(f"background-color: {self.teal}; color: white;")
        self.annotation_button_layout.addWidget(self.freehand_button)
        self.freehand_button.setFixedHeight(button_height)
        self.freehand_button.setFixedWidth(button_width)

        self.square_button = QRadioButton("Square")
        self.square_button.setStyleSheet(f"background-color: {self.teal}; color: white;")
        self.annotation_button_layout.addWidget(self.square_button)
        self.square_button.setFixedHeight(button_height)
        self.square_button.setFixedWidth(button_width)

        self.circle_button = QRadioButton("Circle")
        self.circle_button.setStyleSheet(f"background-color: {self.teal}; color: white;")
        self.annotation_button_layout.addWidget(self.circle_button)
        self.circle_button.setFixedHeight(button_height)
        self.circle_button.setFixedWidth(button_width)

        self.rectangle_button = QRadioButton("Rectangle")
        self.rectangle_button.setStyleSheet(f"background-color: {self.teal}; color: white;")
        self.annotation_button_layout.addWidget(self.rectangle_button)
        self.rectangle_button.setFixedHeight(button_height)
        self.rectangle_button.setFixedWidth(button_width)

        self.triangle_button = QRadioButton("Triangle")
        self.triangle_button.setStyleSheet(f"background-color: {self.teal}; color: white;")
        self.annotation_button_layout.addWidget(self.triangle_button)
        self.triangle_button.setFixedHeight(button_height)
        self.triangle_button.setFixedWidth(button_width)

        self.ellipse_button = QRadioButton("Ellipse")
        self.ellipse_button.setStyleSheet(f"background-color: {self.teal}; color: white;")
        self.annotation_button_layout.addWidget(self.ellipse_button)
        self.ellipse_button.setFixedHeight(button_height)
        self.ellipse_button.setFixedWidth(button_width)
       
        self.hist_button = QPushButton("Histogram Eq")
        self.hist_button.setStyleSheet(f"background-color: {self.teal}; color: white;")
        self.button_layout.addWidget(self.hist_button)
        self.hist_button.setFixedHeight(button_height)
        self.hist_button.setFixedWidth(button_width)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setStyleSheet(f"background-color: {self.teal}; color: white;")
        self.button_layout.addWidget(self.clear_button)
        self.clear_button.setFixedHeight(button_height)
        self.clear_button.setFixedWidth(button_width)

        self.tool_layout.addLayout(self.annotation_button_layout)

        button_style = (
        f"QPushButton {{"
        f"background-color: {self.teal};"
        f"color: white;"  
        f"border: 1px solid white;"
        f"border-radius: 5px;"
        f"padding: 10px;"
        f"}}"
        f"QPushButton:hover {{"
        f"background-color: {self.lightgrey};"
        f"color: {self.teal};"
        f"}}"
        f"QRadioButton {{"
        f"background-color: {self.teal};"
        f"color: white;"  
        f"border: 1px solid white;"
        f"border-radius: 5px;"
        f"padding: 10px;"
        f"}}"
        f"QRadioButton:hover {{"
        f"background-color: {self.lightgrey};"
        f"color: {self.teal};"
        f"}}"
        f"QToolTip {{"
        f"background-color: white;"  
        f"color: black;" 
        f"}}"
    )

        annotation_buttons = [
            self.fullscreen_button,
            self.zoom_in_button,
            self.zoom_out_button,
            self.download_button,
            self.clear_button,
            self.hist_button,
            self.reset_button,
            self.freehand_button,
            self.square_button,
            self.circle_button,
            self.rectangle_button,
            self.triangle_button,
            self.ellipse_button,
        ]
        for button in annotation_buttons:
            button.setStyleSheet(button_style)


        self.fullscreen_button.setToolTip("Toggle fullscreen mode")
        self.zoom_in_button.setToolTip("Zoom in on the image")
        self.zoom_out_button.setToolTip("Zoom out on the image")
        self.download_button.setToolTip("Download the annotated image")
        self.clear_button.setToolTip("Clear all annotations")
        self.hist_button.setToolTip("Apply histogram equalization (grayscale the image)")
        self.reset_button.setToolTip("Restore the original colored image")
        self.freehand_button.setToolTip("Draw annotations freehand")
        self.square_button.setToolTip("Draw square annotations")
        self.circle_button.setToolTip("Draw circular annotations")
        self.rectangle_button.setToolTip("Draw rectangular annotations")
        self.triangle_button.setToolTip("Draw triangular annotations")
        self.ellipse_button.setToolTip("Draw elliptical annotations")

        self.annotation_type = AnnotationType.NONE
        self.annotation_color = QColor("red")
        self.annotation_items = []

        logo_pixmap = QPixmap("/Users/maana/Downloads/Medical-Image-Analysis-GUI/BooleanLab copy.jpeg")
        logo_pixmap = logo_pixmap.scaledToWidth(100)
        self.logo_label = QLabel()
        self.logo_label.setPixmap(logo_pixmap)
        self.alignment_widget = QWidget(self)
        self.alignment_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.alignment_layout = QVBoxLayout(self.alignment_widget)
        self.alignment_layout.addWidget(self.logo_label, alignment=Qt.AlignBottom | Qt.AlignRight)
        self.layout.addWidget(self.alignment_widget, 2, 1, alignment=Qt.AlignBottom | Qt.AlignRight)

        self.original_image_path = None

        self.setup_actions()
        self.connect_signals()

    def setup_actions(self):
        self.zoom_in_action = QAction("Zoom In", self)
        self.zoom_out_action = QAction("Zoom Out", self)
        self.download_action = QAction("Download", self)

        self.zoom_in_action.triggered.connect(self.zoom_in)
        self.zoom_out_action.triggered.connect(self.zoom_out)
        self.download_action.triggered.connect(self.download_image)

        self.addAction(self.zoom_in_action)
        self.addAction(self.zoom_out_action)
        self.addAction(self.download_action)

    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.showNormal()
            self.is_fullscreen = False
        else:
            self.showFullScreen()
            self.is_fullscreen = True

    def connect_signals(self):
        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self.download_button.clicked.connect(self.download_image)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.clear_button.clicked.connect(self.clear_annotations)
        self.hist_button.clicked.connect(self.apply_histogram_equalization)
        self.reset_button.clicked.connect(self.reset_image)

        self.freehand_button.clicked.connect(lambda: self.annotation_view.set_annotation_type(AnnotationType.FREEHAND))
        self.square_button.clicked.connect(lambda: self.annotation_view.set_annotation_type(AnnotationType.SQUARE))
        self.circle_button.clicked.connect(lambda: self.annotation_view.set_annotation_type(AnnotationType.CIRCLE))
        self.rectangle_button.clicked.connect(lambda: self.annotation_view.set_annotation_type(AnnotationType.RECTANGLE))
        self.triangle_button.clicked.connect(lambda: self.annotation_view.set_annotation_type(AnnotationType.TRIANGLE))
        self.ellipse_button.clicked.connect(lambda: self.annotation_view.set_annotation_type(AnnotationType.ELLIPSE))

    def set_image(self, image_path):
        pixmap = QPixmap(image_path)
        self.original_image_path = image_path
        self.original_pixmap = pixmap
        self.image_label.setPixmap(pixmap)
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.annotation_view.resetTransform()
        self.annotation_view.scale(self.initial_zoom_factor, self.initial_zoom_factor)

    def clear_annotations(self):

        image_pixmap = self.image_label.pixmap()
        image_scene = QGraphicsScene(self)
        image_scene.setSceneRect(0, 0, image_pixmap.width(), image_pixmap.height())
        image_item = QGraphicsPixmapItem(image_pixmap)
        image_scene.addItem(image_item)

        self.annotation_view.setScene(image_scene)

    def zoom_in(self):
        self.annotation_view.scale(1.2, 1.2)

    def zoom_out(self):
        self.annotation_view.scale(0.8, 0.8)

    def clear_annotation_items(self):
        self.annotation_items.clear()

    def download_image(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Image", "", "PNG Images (*.png);;All Files (*)", options=options
        )

        if file_name:
            pixmap = QPixmap(self.scene.sceneRect().size().toSize())
            pixmap.fill(Qt.white)
            painter = QPainter(pixmap)
            self.scene.render(painter)

            for item in self.annotation_items:
                item.paint(painter, None, None)

            painter.end()
            pixmap.save(file_name, "PNG")
            print(f"Image with annotations saved as {file_name}")


    def apply_histogram_equalization(self):
        if self.original_image_path:
            original_image = cv2.imread(self.original_image_path, cv2.IMREAD_GRAYSCALE)
            if original_image is None:
                print(f"Failed to load the image from {self.original_image_path}")
                return

            equalized_image = cv2.equalizeHist(original_image)
            height, width = equalized_image.shape
            bytes_per_line = width
            q_image = QImage(equalized_image.data, width, height, bytes_per_line, QImage.Format_Grayscale8)

            pixmap = QPixmap.fromImage(q_image)

            self.image_label.setPixmap(pixmap) 
            self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
            self.annotation_view.resetTransform()
            self.annotation_view.scale(self.initial_zoom_factor, self.initial_zoom_factor)

    def reset_image(self):
        if self.original_pixmap:
            self.image_label.setPixmap(self.original_pixmap)
            self.scene.setSceneRect(0, 0, self.original_pixmap.width(), self.original_pixmap.height())
            self.annotation_view.resetTransform()
            self.annotation_view.scale(self.initial_zoom_factor, self.initial_zoom_factor)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AnnotationMainWindow()

    image_path = "/Users/maana/Downloads/Medical-Image-Analysis-GUI/MicrosoftTeams-image.png"
    window.set_image(image_path)
    window.show()

    sys.exit(app.exec_())
