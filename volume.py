import pathlib
import numpy as np
from utils import Utils
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
import cv2
import nrrd
import nrrd.writer
import time

# The nrrd writer provided by the pynrrd package duplicates
# the data in memory before writing.  This is undesirable
# for large data volumes.  The code below overrides the
# original nrrd write function, to avoid data duplication in
# the particular case that is used by the TIFF importer.

# save the original version of the nrrd writer
nrrd_write_data_original = nrrd.writer._write_data

# original function signature, with types:
# def _write_data(data: npt.NDArray, fh: IO, header: NRRDHeader, compression_level: Optional[int] = None,

# overriding function
def nrrd_write_data_override(data, fh, header, compression_level=None, index_order='F'):
    print("nrrd_write_data_override", header['encoding'], index_order)
    if header['encoding'] == 'raw' and index_order == 'C':
        print("nrrd_write_data_override: doing direct write")
        # write without duplicating data
        data.tofile(fh)
    else:
        # call the original nrrd write function
        nrrd_write_data_original(data, fh, header, compression_level, index_order)

nrrd.writer._write_data = nrrd_write_data_override

# end of code to override pynrrd functionality

class ColorSelectorDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, table, parent=None):
        super(ColorSelectorDelegate, self).__init__(parent)
        self.table = table
        # self.color = QColor()

    def createEditor(self, parent, option, index):
        # print("ce csd", index.row())
        cb = QtWidgets.QPushButton(parent)
        cb.setContentsMargins(5,5,5,5)
        cb.clicked.connect(lambda d: self.onClicked(d, cb, index))
        return cb

    def onClicked(self, cb_index, push_button, model_index):
        old_color = push_button.palette().color(QtGui.QPalette.Window)
        new_color = QtWidgets.QColorDialog.getColor(old_color, self.table)
        # print("old_color",old_color.name(),"new_color",new_color.name())
        if new_color.isValid() and new_color != old_color:
            self.setColor(push_button, new_color.name())
            self.table.model().setData(model_index, new_color, Qt.EditRole)

    # this could be a class function
    def setColor(self, push_button, color):
        # color is a string, not a qcolor
        # print("pb setting color", color)
        push_button.setStyleSheet("background-color: %s"%color)

    def setEditorData(self, editor, index):
        # print("sed", index.row(), index.data(Qt.EditRole))
        # print("sed", index.row(), index.data(Qt.DisplayRole))
        color = index.data(Qt.DisplayRole)
        # color is a string
        if color:
            # editor.setCurrentIndex(cb_index)
            self.setColor(editor, color)

    def setModelData(self, editor, model, index):
        old_color = editor.palette().color(QtGui.QPalette.Window)
        # print("csd smd", old_color.name())

    def displayText(self, value, locale):
        return ""


class DirectionSelectorDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, table, parent=None):
        super(DirectionSelectorDelegate, self).__init__(parent)
        self.table = table

    def createEditor(self, parent, option, index):
        # print("ce dsd", index.row())
        cb = QtWidgets.QComboBox(parent)
        # row = index.row()
        cb.addItem("X")
        cb.addItem("Y")
        cb.activated.connect(lambda d: self.onActivated(d, cb, index))
        return cb

    def onActivated(self, cb_index, combo_box, model_index):
        self.table.model().setData(model_index, combo_box.currentText(), Qt.EditRole)

    def setEditorData(self, editor, index):
        # print("sed", index.row(), index.data(Qt.EditRole))
        # print("sed", index.row(), index.data(Qt.DisplayRole))
        cb_index = index.data(Qt.DisplayRole)
        if cb_index >= 0:
            editor.setCurrentIndex(cb_index)
        # return editor
        # for i in range(15):
        #     print(i, index.data(i))
        # otxt = index.data(Qt.EditRole)
        # cb_index = editor.findText(otxt)
        # if index >= 0:
        #     editor.setCurrentIndex(index)
        # return editor

    def setModelData(self, editor, model, index):
        pass
        # print("smd", editor.currentText())
        # do nothing, since onActivated handled it
        # model.setData(index, editor.currentText(), Qt.EditRole)

class OpacitySelectorDelegate(QtWidgets.QStyledItemDelegate):

    def __init__(self, table, parent=None):
        super(OpacitySelectorDelegate, self).__init__(parent)
        self.table = table

    def createEditor(self, parent, option, index):
        # print("ce osd", index.row())
        sb = QtWidgets.QDoubleSpinBox(parent)
        sb.setMinimum(0.0)
        sb.setMaximum(1.0)
        sb.setDecimals(1)
        sb.setSingleStep(0.1)
        sb.valueChanged.connect(lambda d: self.onValueChanged(d, sb, index), Qt.QueuedConnection)
        sb.kh_value = -1.
        sb.setValue(.5)
        return sb

    def onValueChanged(self, value, spin_box, model_index):
        # print("ovc", spin_box.value(), value)
        if spin_box.kh_value == value:
            spin_box.lineEdit().deselect()
            return
        # if spin_box.value() == value:
        #     print("exiting ovc")
        #     return
        self.table.model().setData(model_index, spin_box.value(), Qt.EditRole)
        # print("leaving ovc", spin_box.value())
        spin_box.kh_value = value
        spin_box.lineEdit().deselect()

    def setEditorData(self, editor, index):
        # print("sed")
        opacity = index.data(Qt.DisplayRole)
        editor.lineEdit().deselect()
        if opacity is not None:
            if editor.value() != opacity:
                oev = editor.value()
                octxt = editor.cleanText()
                editor.kh_value = opacity
                editor.setValue(opacity)
                # print(oev, octxt, opacity, editor.value())
                # time.sleep(1)

    def setModelData(self, editor, model, index):
        # opacity = index.data(Qt.DisplayRole)
        # print("smd", opacity, editor.value())
        pass

class MinMaxSelectorDelegate(QtWidgets.QStyledItemDelegate):

    def __init__(self, table, parent=None):
        super(MinMaxSelectorDelegate, self).__init__(parent)
        self.table = table

    def createEditor(self, parent, option, index):
        sb = QtWidgets.QSpinBox(parent)
        sb.setMinimum(0)
        sb.setMaximum(255)
        sb.setSingleStep(1)
        sb.valueChanged.connect(lambda d: self.onValueChanged(d, sb, index), Qt.QueuedConnection)
        sb.kh_value = -1.
        sb.setValue(1)
        # print("ce", sb.value())
        return sb

    def onValueChanged(self, value, spin_box, model_index):
        # print("vch", value, spin_box.kh_value, spin_box.value())
        if spin_box.kh_value == value:
            # spin_box.lineEdit().deselect()
            return
        self.table.model().setData(model_index, spin_box.value(), Qt.EditRole)
        # value is the new value requested by the spin box;
        # changed_value is the value actually set in response.
        # If changed_value is different than requested,
        # set the spin box value to changed_value
        changed_value = model_index.data(Qt.DisplayRole)
        if changed_value != value:
            # This seems recursive since it causes a call to
            # onValueChange.  But the call passes through an event
            # queue, so it is not directly recursive.  I think...
            spin_box.setValue(changed_value)
        spin_box.kh_value = value
        spin_box.lineEdit().deselect()

    def setEditorData(self, editor, index):
        minmax = index.data(Qt.DisplayRole)
        # print("sed", minmax)
        if minmax is not None:
            if editor.value() != minmax:
                oev = editor.value()
                octxt = editor.cleanText()
                editor.kh_value = minmax
                editor.setValue(minmax)

    def setModelData(self, editor, model, index):
        pass

class ColormapSelectorDelegate(QtWidgets.QStyledItemDelegate):
    colormaps = {
            "gray": "matlab:gray",
            "viridis": "bids:viridis",
            "bwr": "matplotlib:bwr",
            "cool": "matlab:cool",
            "bmr_3c": "chrisluts:bmr_3c",
            "rainbow": "gnuplot:rainbow",
            }

    def __init__(self, table, parent=None):
        super(ColormapSelectorDelegate, self).__init__(parent)
        self.table = table

    def createEditor(self, parent, option, index):
        # print("ce cmsd", index.row())
        cb = QtWidgets.QComboBox(parent)
        # row = index.row()
        for key in self.colormaps.keys():
            cb.addItem(key)
        cb.activated.connect(lambda d: self.onActivated(d, cb, index))
        return cb

    def onActivated(self, value, combo_box, model_index):
        self.table.model().setData(model_index, combo_box.itemText(value), Qt.EditRole)

    def setEditorData(self, editor, index):
        colormap = index.data(Qt.DisplayRole)
        if colormap:
            # editor.setCurrentIndex(cb_index)
            self.setColormap(editor, colormap)

    # this could be a class function
    def setColormap(self, cb, colormap):
        # colormap is a string like "matplotlib:bwr"
        # we want to display the corresponding short name
        # print("setColormap", colormap)
        for key, value in self.colormaps.items():
            if value == colormap:
                # print("   ", key)
                cb.setCurrentText(key)
                break

    def setModelData(self, editor, model, index):
        # do nothing, since onActivated handled it
        pass

class VolumesModel(QtCore.QAbstractTableModel):
    def __init__(self, project_view, main_window):
        super(VolumesModel, self).__init__()
        # note that self.project_view should not be
        # changed after initialization; instead, a new
        # instance of VolumesModel should be created
        # and attached to the QTableView
        self.project_view = project_view
        self.main_window = main_window

    '''
    columns = [
            "Base",
            "Name",
            "Color",
            "Ld",
            "Dir",
            "X min",
            "X max",
            "dX",
            "Y min",
            "Y max",
            "dY",
            "Z min",
            "Z max",
            "dZ",
            "Gb",
            ]
    '''

    columns = [
            "Base",
            "O1",
            "O2",
            "Name",
            "Color",
            "Opacity",
            "Colormap",
            "Min",
            "Max",
            "Ind",
            "Ld",
            "Dir",
            "Info"
            ]

    '''
    ctips = [
            "Select which volume is visible;\nclick box to select",
            "Select overlay volume;\nclick box to select",
            "Select second overlay volume;\nclick box to select",
            "Name of the volume",
            "Color of the volume outline drawn on slices;\nclick to edit",
            "Is volume currently loaded in memory\n(volumes that are not currently displayed\nare unloaded by default)",
            """Direction (orientation) of the volume;
X means that the X axis in the original tiff 
files is aligned with the vertical axes of the slice
displays; Y means that the Y axis in the original
tiff files is aligned with the slice vertical axes""",
            "Minimum X coordinate of the volume,\nrelative to tiff coordinates",
            "Maximum X coordinate of the volume,\nrelative to tiff coordinates",
            "X step (number of pixels stepped\nin the X direction in the tiff image\nfor each pixel in the slices)",
            "Minimum Y coordinate of the volume,\nrelative to tiff coordinates",
            "Maximum Y coordinate of the volume,\nrelative to tiff coordinates",
            "Y step (number of pixels stepped\nin the X direction in the tiff image\nfor each pixel in the slices)",
            "Minimum Z coordinate (image number) of the volume",
            "Maximum Z coordinate (image number) of the volume",
            "Z step (number of tiff images stepped for each slice image)",
            "Data size in Gb (10^9 bytes)",
            ]
    '''
    ctips = [
            "Select which volume is visible;\nclick box to select",
            "O1",
            "O2",
            "Name of the volume",
            "Color of the volume outline drawn on slices;\nclick to edit",
            "Opacity if overlaid (0.0 transparent, 1.0 opaque)",
            "Colormap",
            "Colormap range minimum value (0 or more)",
            "Colormap range maximum value (255 or less)",
            "Is volume data of type 'indicator' (rather than 'continuous')",
            "Is volume currently loaded in memory\n(volumes that are not currently displayed\nare unloaded by default)",
            """Direction (orientation) of the volume;
X means that the X axis in the original tiff 
files is aligned with the vertical axes of the slice
displays; Y means that the Y axis in the original
tiff files is aligned with the slice vertical axes""",
            "Hover over the ⓘ for more info"
    ]

    @staticmethod
    def columnIndex(name):
        return VolumesModel.columns.index(name)

    @staticmethod
    def columnIndices(names):
        inds = []
        for name in names:
            inds.append(VolumesModel.columnIndex(name))
        return inds
    
    def flags(self, index):
        col = index.column()
        # if col in (0,1,2):
        #     return Qt.ItemIsEditable|Qt.ItemIsEnabled
        oflags = super(VolumesModel, self).flags(index)
        if col in self.columnIndices(["Base", "O1", "O2", "Ind"]):
            # print(col, int(oflags))
            nflags = Qt.ItemNeverHasChildren
            nflags |= Qt.ItemIsUserCheckable
            nflags |= Qt.ItemIsEnabled
            # nflags |= Qt.ItemIsEditable
            return nflags
        elif col in self.columnIndices(["Color", "Dir", "Opacity", "Min", "Max", "Colormap"]):
            nflags = Qt.ItemNeverHasChildren
            # nflags |= Qt.ItemIsUserCheckable
            nflags |= Qt.ItemIsEnabled
            # nflags |= Qt.ItemIsEditable
            return nflags
        else:
            return Qt.ItemNeverHasChildren|Qt.ItemIsEnabled

    def headerData(self, section, orientation, role):
        if orientation != Qt.Horizontal:
            return None
        
        if role == Qt.DisplayRole:
            if section == 0:
                # print("HD", self.rowCount())
                table = self.main_window.volumes_table
                # make sure the combo box in column 4 is always open
                # (so no double-clicking required)
                for i in range(self.rowCount()):
                    index = self.createIndex(i, self.columnIndex("Color"))
                    table.openPersistentEditor(index)
                    index = self.createIndex(i, self.columnIndex("Dir"))
                    table.openPersistentEditor(index)
                    index = self.createIndex(i, self.columnIndex("Colormap"))
                    table.openPersistentEditor(index)
                    index = self.createIndex(i, self.columnIndex("Opacity"))
                    table.openPersistentEditor(index)
                    index = self.createIndex(i, self.columnIndex("Min"))
                    table.openPersistentEditor(index)
                    index = self.createIndex(i, self.columnIndex("Max"))
                    table.openPersistentEditor(index)

            return VolumesModel.columns[section]
        elif role == Qt.ToolTipRole:
            return VolumesModel.ctips[section]

    def columnCount(self, parent=None):
        return len(VolumesModel.columns)

    def rowCount(self, parent=None):
        if self.project_view is None:
            return 0
        volumes = self.project_view.volumes
        return len(volumes.keys())

    # columns: name, color, direction, xmin, xmax, xstep, y..., img...

    def data(self, index, role):
        if self.project_view is None:
            return None
        if role == Qt.DisplayRole:
            return self.dataDisplayRole(index, role)
        elif role == Qt.TextAlignmentRole:
            return self.dataAlignmentRole(index, role)
        elif role == Qt.BackgroundRole:
            return self.dataBackgroundRole(index, role)
        elif role == Qt.CheckStateRole:
            return self.dataCheckStateRole(index, role)
        elif role == Qt.ToolTipRole:
            return self.ToolTipRole(index, role)
        return None

    def dataCheckStateRole(self, index, role):
        column = index.column()
        row = index.row()
        volumes = self.project_view.volumes
        # volume = list(volumes.keys())[row]
        volume_view = list(volumes.values())[row]
        # selected = (self.project_view.cur_volume == volume)
        if column in self.columnIndices(["Base", "O1", "O2"]):
            ovv = self.getVolumeViewOrOverlay(column)
            if ovv == volume_view:
                return Qt.Checked
            else:
                return Qt.Unchecked
        if column in self.columnIndices(["Ind"]):
            if volume_view.colormap_is_indicator:
                return Qt.Checked
            else:
                return Qt.Unchecked

    def dataAlignmentRole(self, index, role):
        # column = index.column()
        # if column >= 4:
        #     return Qt.AlignVCenter + Qt.AlignRight
        return Qt.AlignVCenter + Qt.AlignRight

    def dataBackgroundRole(self, index, role):
        row = index.row()
        volumes = self.project_view.volumes
        volume = list(volumes.keys())[row]
        if self.project_view.cur_volume == volume:
            return QtGui.QColor(self.main_window.highlightedBackgroundColor())

    def dataDisplayRole(self, index, role):
        row = index.row()
        column = index.column()
        volumes = self.project_view.volumes
        volume = list(volumes.keys())[row]
        volume_view = volumes[volume]
        mins = volume.gijk_starts
        steps = volume.gijk_steps 
        sizes = volume.sizes
        selected = (self.project_view.cur_volume == volume)
        if column == self.columnIndex("Name"):
            return volume.name
        elif column == self.columnIndex("Color"):
            return volume_view.color.name()
        elif column == self.columnIndex("Colormap"):
            # print("ddr cmn", volume_view.colormap_name)
            return volume_view.colormap_name
        elif column == self.columnIndex("Ld"):
            if volume.data is None:
                return 'No'
            else:
                return 'Yes'
        elif column == self.columnIndex("Dir"):
            # return "%s"%(('X','Y')[volume_view.direction])
            # print("data display role", row, volume_view.direction)
            return (0,1)[volume_view.direction]
        elif column == self.columnIndex("Opacity"):
            # print("ddr", volume_view.opacity)
            return volume_view.opacity
        elif column == self.columnIndex("Min"):
            # print("ddr mn", volume_view.getColormapIntMin())
            return volume_view.getColormapIntMin()
        elif column == self.columnIndex("Max"):
            # print("ddr mx", volume_view.getColormapIntMax())
            return volume_view.getColormapIntMax()

            '''
        elif column >= 5 and column < 14:
            i3 = column-5
            i = i3//3
            j = i3 %3
            x0 = mins[i]
            dx = steps[i]
            nx = sizes[i]
            if j == 0:
                return x0
            elif j == 1:
                return x0+dx*(nx-1)
            else:
                return dx
        elif column == 14:
            gb = volume.dataSize()/1000000000
            # print(volume.name,gb)
            return "%0.1f"%gb
            '''

        elif column == self.columnIndex("Info"):
            return "ⓘ"

        else:
            return None

    def ToolTipRole(self, index, role):
        row = index.row()
        column = index.column()
        if column != self.columnIndex("Info"):
            return
        volumes = self.project_view.volumes
        volume = list(volumes.keys())[row]
        volume_view = volumes[volume]
        mins = volume.gijk_starts
        steps = volume.gijk_steps 
        sizes = volume.sizes
        # dtype_str = volume.dtype_str
        dtype_str = str(volume.dtype)
        zarr_str = ""
        if volume.is_zarr:
            zarr_str = " (zarr)"
        gb = volume.dataSize()/1000000000
        # maxes = [mins[i]+steps[i]*(sizes[i]-1) for i in range(3)]
        ostr = ""
        axs = ["X", "Y", "Z"]
        for i in range(3):
            mn = mins[i]
            d = steps[i]
            n = sizes[i]
            mx = mn+d*(n-1)
            ax = axs[i]
            lstr = "%s: min %d, max %d, step %d\n" % (ax, mn, mx, d)
            ostr += lstr
        ostr += "%0.1f Gb%s, data type %s"%(gb, zarr_str, dtype_str)
        return ostr

    def getVolumeViewOrOverlay(self, col_index):
        name = self.columns[col_index]
        pv = self.project_view
        if name == "Base":
            # self.main_window.setVolume(volume)
            return pv.cur_volume_view
        elif name == "O1":
            # self.main_window.setOverlay(0, volume)
            return pv.overlay_volume_views[0]
        elif name == "O2":
            return pv.overlay_volume_views[1]

    def setVolumeOrOverlay(self, col_index, volume):
        name = self.columns[col_index]
        if name == "Base":
            self.main_window.setVolume(volume)
        elif name == "O1":
            self.main_window.setOverlay(0, volume)
        elif name == "O2":
            self.main_window.setOverlay(1, volume)

    def setData(self, index, value, role):
        row = index.row()
        column = index.column()
        # print("setdata", row, column, value, role)
        # if role != Qt.EditRole:
        #     return False
        volumes = self.project_view.volumes
        volume = list(volumes.keys())[row]
        volume_view = volumes[volume]
        if role == Qt.CheckStateRole and column in self.columnIndices(["Base", "O1", "O2"]):
            # print(row, value)
            cv = Qt.CheckState(value)
            if cv != Qt.Checked:
                # self.main_window.setVolume(None)
                self.setVolumeOrOverlay(column, None)
                return False
            # volumes = self.project_view.volumes
            # volume = list(volumes.keys())[row]
            # volume_view = volumes[volume]
            # self.main_window.setVolume(volume)
            self.setVolumeOrOverlay(column, volume)
            # return True
        elif role == Qt.CheckStateRole and column in self.columnIndices(["Ind"]):
            cv = Qt.CheckState(value)
            self.main_window.setColormapIsIndicator(volume_view, cv == Qt.Checked)
        elif role == Qt.EditRole and column == self.columnIndex("Color"):
            color = value
            # volumes = self.project_view.volumes
            # volume = list(volumes.keys())[row]
            # volume_view = volumes[volume]
            # print("setdata", row, color.name())
            # volume_view.setColor(color)
            self.main_window.setVolumeViewColor(volume_view, color)
        elif role == Qt.EditRole and column == self.columnIndex("Dir"):
            # print("setdata", row, value)
            direction = 0
            if value == 'Y':
                direction = 1
            # volumes = self.project_view.volumes
            # volume = list(volumes.keys())[row]
            self.main_window.setDirection(volume, direction)
        elif role == Qt.EditRole and column == self.columnIndex("Opacity"):
            # volumes = self.project_view.volumes
            # volume_view = list(volumes.values())[row]
            self.main_window.setVolumeViewOpacity(volume_view, value)
        elif role == Qt.EditRole and column == self.columnIndex("Min"):
            self.main_window.setVolumeViewColormapIntMin(volume_view, value)
        elif role == Qt.EditRole and column == self.columnIndex("Max"):
            self.main_window.setVolumeViewColormapIntMax(volume_view, value)
        elif role == Qt.EditRole and column == self.columnIndex("Colormap"):
            # print("setdata", row, value)
            short_name = value
            full_name = ColormapSelectorDelegate.colormaps[short_name]
            # volumes = self.project_view.volumes
            # volume_view = list(volumes.values())[row]
            self.main_window.setVolumeViewColormap(volume_view, full_name)

        return False


class VolumeView():

    def __init__(self, project_view, volume):
        self.project_view = project_view
        self.volume = volume
        self.direction = 1
        self.trdata = None
        # itf, jtf, ktf are i,j,k of focus point (crosshairs)
        # in transposed-grid coordinates
        # so focus pixel = datatr[ktf, jtf, itf]
        self.ijktf = (0,0,0)
        self.last_jump_ijktf = None
        # self.stxytf = (0.,0.)
        self.stxytf = None
        self.zoom = 0.
        self.minZoom = 0.
        self.maxZoom = 5
        # It would seem to make more sense to attach the
        # color to Volume, rather than to VolumeView, just as
        # a fragment's color is attached to Fragment rather
        # than to FragmentView.
        # However, if a user changes a volume's color, we
        # don't want to have to re-write the entire NRRD file.
        # So associate color with VolumeView instead, which
        # means it is stored in the project-view file
        self.color = None
        color = Utils.getNextColor()
        self.setColor(color, no_notify=True)
        # self.color = QColor()
        # self.cvcolor = (0,0,0,0)
        # Same for opacity as for color
        self.opacity = 1.

        self.colormap_range = [0., 1.]
        self.colormap_name = ""
        self.colormap_lut = None
        self.colormap_lut_timestamp = Utils.timestamp()
        if volume.uses_overlay_colormap:
            self.colormap_is_indicator = True
        else:
            self.colormap_is_indicator = False

    def setColormapRange(self, mn, mx, no_notify=False):
        changed = False
        if mx is not None:
            mx = min(1., mx)
            mx = max(0., mx)
            if self.colormap_range[1] != mx:
                self.colormap_range[1] = mx
                changed = True
        if mn is not None:
            if mx is None:
                mx = self.colormap_range[1]
            mn = min(1., mn)
            mn = max(0., mn)
            mn = min(mn, mx)
            if self.colormap_range[0] != mn:
                self.colormap_range[0] = mn
                changed = True
        if changed:
            v = self.volume
            cmap = Utils.ColorMap(self.colormap_name, v.dtype, 1., self.colormap_range)
            self.colormap_lut = cmap.lut
            self.colormap_lut_timestamp = Utils.timestamp()
            if not no_notify:
                self.notifyModified()

    def getColormapIntMin(self):
        return int(round(self.colormap_range[0]*255))

    def getColormapIntMax(self):
        return int(round(self.colormap_range[1]*255))

    def setColormapIntMin(self, value):
        mx = self.getColormapIntMax()
        if value > mx:
            return
        mn = value/255.
        # print("setting mn to", mn)
        self.setColormapRange(mn, None)

    def setColormapIntMax(self, value):
        mn = self.getColormapIntMin()
        # print("mx value mn", value, mn)
        if value < mn:
            return
        mx = value/255.
        # print("setting mx to", mx)
        self.setColormapRange(None, mx)

    def notifyModified(self, tstamp=""):
        if tstamp == "":
            tstamp = Utils.timestamp()
        # print("volume view modified", tstamp)
        self.project_view.notifyModified(tstamp)

    def setColor(self, qcolor, no_notify=False):
        if self.color == qcolor:
            return
        self.color = qcolor
        rgba = qcolor.getRgbF()
        self.cvcolor = [int(65535*c) for c in rgba] 
        if not no_notify:
            self.notifyModified()

    '''
    def setColormap(self, force_set=False):
        v = self.volume
        if not v.can_modify_colormap and not force_set:
            return
        print("setColormap", self.colormap_name)
        cmap = Utils.ColorMap(self.colormap_name, v.dtype, 1., self.colormap_range)
        self.colormap_lut = cmap.lut
        self.colormap_lut_timestamp = Utils.timestamp()
    '''

    def setColormap(self, colormap_name, no_notify=False):
        if self.colormap_name == colormap_name:
            return
        v = self.volume
        # False if "uses_overlay_colormap" is set
        if not v.can_modify_colormap:
            return
        self.colormap_name = colormap_name
        # print("setColormap", self.colormap_name)
        cmap = Utils.ColorMap(colormap_name, v.dtype, 1., self.colormap_range)
        self.colormap_lut = cmap.lut
        self.colormap_lut_timestamp = Utils.timestamp()
        if not no_notify:
            self.notifyModified()

    def setColormapIsIndicator(self, flag, no_notify=False):
        if self.colormap_is_indicator == flag:
            return
        self.colormap_is_indicator = flag;
        if not no_notify:
            self.notifyModified()

    def setOpacity(self, opacity, no_notify=False):
        # print("so", self.opacity, opacity)
        if self.opacity == opacity:
            return
        self.opacity = opacity
        if not no_notify:
            self.notifyModified()

    def setZoom(self, zoom):
        self.zoom = min(self.maxZoom, max(zoom, self.minZoom))
        self.notifyModified()

    # direction=0: "depth" slice is constant-x (y,z plane)
    # direction=1: "depth" slice is constant-y (z,x plane)
    # Another way to look at it is direction=0 means
    # that the X axis of the original tiff images is aligned
    # with the vertical axis in the top two slices;
    # direction=1 means that the Y axis of the original tiff
    # images is vertical.
    # original data is accessed as [slice, y, x]
    # note that origin of image is upper-left corner
    # image is accessed as [y, x]
    # call after data is loaded
    def setDirection(self, direction):
        if self.direction != direction:
            ijk = self.ijktf
            self.ijktf = (ijk[2], ijk[1], ijk[0])
            self.stxytf = None
            self.clearLastJumpIjkTf()
        self.direction = direction
        if self.volume.data is not None:
            self.trdata = self.volume.trdatas[direction]
            self.trshape = self.trdata.shape[:3]
            self.notifyModified()
        else:
            print("warning, VolumeView.setDirection: volume data is not loaded")
            self.trdata = None

    def dataLoaded(self):
        self.trdata = self.volume.trdatas[self.direction]
        self.trshape = self.trdata.shape[:3]

    # call after direction is set
    def getDefaultZoom(self, window, zarr_max_width):
        # depth, xline, inline = self.getSlices((0,0,0))
        depth_shape, xline_shape, inline_shape = self.getSliceShapes(zarr_max_width)
        minzoom = 0.
        for sh,sz in zip(
              # [depth.shape, xline.shape, inline.shape],
              [depth_shape, xline_shape, inline_shape],
              [window.depth.size(), window.xline.size(), window.inline.size()]):
            # print(sh,sz)
            shx = sh[1]
            szx = sz.width()
            shy = sh[0]
            szy = sz.height()
            mn = min(szx/shx, szy/shy)
            if minzoom == 0 or mn < minzoom:
                minzoom = mn
        # print("minzoom", minzoom)
        return minzoom

    def setDefaultMinZoom(self, window, zarr_max_width):
        dzoom = self.getDefaultZoom(window, zarr_max_width)*self.volume.averageStepSize()
        asz = self.volume.averageStepSize()
        self.minZoom = min(.05, .5*dzoom)
        self.maxZoom = 5*asz

    # call after direction is set
    def setDefaultParameters(self, window, zarr_max_width, no_notify=False):
        # zoom=1 means one pixel in grid should
        # be the same size as one pixel in viewing window
        self.zoom = self.getDefaultZoom(window, zarr_max_width)
        # self.minZoom = .5*self.zoom
        # self.maxZoom = 5*self.volume.averageStepSize()
        if self.volume.is_zarr:
            sh = self.trshape
        else:
            sh = self.trdata.shape
        # itf, jtf, ktf are ijk of focus point in tranposed grid
        # value at focus point is trdata[ktf,jtf,itf]
        itf = int(sh[2]/2)
        jtf = int(sh[1]/2)
        ktf = int(sh[0]/2)
        self.ijktf = (itf, jtf, ktf)
        self.clearLastJumpIjkTf()

        gi,gj,gk = self.transposedIjkToGlobalPosition(
                self.ijktf)
        print("global position x %d y %d image %d"%(gi,gj,gk))
        if not no_notify:
            self.notifyModified()

    def setLastJumpIjkTf(self, tf):
        self.last_jump_ijktf = tf

    def returnToLastJumpIjkTf(self):
        lj = self.last_jump_ijktf
        if lj is None:
            return
        self.ijktf = lj
        self.notifyModified()

    def clearLastJumpIjkTf(self):
        self.last_jump_ijktf = None

    def setIjkTf(self, tf):
        o = [0,0,0]

        if self.volume.is_zarr:
            sh = self.trshape
        else:
            sh = self.trdata.shape

        for i in range(0,3):
            t = round(tf[i])
            m = sh[2-i] - 1
            t = min(m, max(t,0))
            o[i] = t
        # self.last_jump_ijktf = self.ijktf
        self.ijktf = tuple(o)
        self.notifyModified()

    def setStxyTf(self, stxy):
        self.stxytf = stxy

    def unsetStxyTf(self):
        self.stxytf = None

    def ijkToTransposedIjk(self, ijk):
        return self.volume.ijkToTransposedIjk(ijk, self.direction)

    def transposedIjkToIjk(self, ijkt):
        return self.volume.transposedIjkToIjk(ijkt, self.direction)

    def transposedIjksToGlobalPositions(self, ijkts):
        return self.volume.transposedIjksToGlobalPositions(ijkts, self.direction)

    def transposedIjkToGlobalPosition(self, ijkt):
        return self.volume.transposedIjkToGlobalPosition(ijkt, self.direction)

    def globalPositionsToTransposedIjks(self, gpoints):
        return self.volume.globalPositionsToTransposedIjks(gpoints, self.direction)

    def globalPositionToTransposedIjk(self, gpoint):
        return self.volume.globalPositionToTransposedIjk(gpoint, self.direction)

    def globalAxisFromTransposedAxis(self, axis):
        return self.volume.globalAxisFromTransposedAxis(axis, self.direction)

    def getSliceInRange(self, data, islice, jslice, k, axis):
        return self.volume.getSliceInRange(data, islice, jslice, k, axis)

    def paintSlice(self, out, axis, ijkt, zoom, zarr_max_width):
        return self.volume.paintSlice(out, axis, ijkt, zoom, zarr_max_width, self.direction)

    def getSlices(self, ijkt):
        return self.volume.getSlices(ijkt, self.direction)

    def getSliceShapes(self, zarr_max_width):
        return self.volume.getSliceShapes(zarr_max_width, self.direction)

    def getSliceBounds(self, axis, ijkt, zarr_max_width):
        return self.volume.getSliceBounds(axis, ijkt, zarr_max_width, self.direction)

class TransposedDataView():
    def __init__(self, data, direction=0):
        self.direction = direction
        data4d = data[:,:,:,np.newaxis]
        if direction == 0:
            self.data = data4d.transpose(2,0,1,3)
        else:
            self.data = data4d.transpose(1,0,2,3)

    @property
    def shape(self):
        return self.data.shape

    @property
    def dtype(self):
        return self.data.dtype

    def __getitem__(self, selection):
        result = self.data[selection]
        return result

class Volume():

    def __init__(self):
        self.data = None
        self.trdatas = None
        self.data_header = None
        self.is_zarr = False
        self.is_streaming = False
        self.valid = False
        self.error = "no error message set"
        self.active_project_views = set()
        self.from_vc_render = False
        self.uses_overlay_colormap = False
        # self.can_modify_colormap = False
        self.can_modify_colormap = True
        # self.colormap_name = ""
        # self.colormap = None
        # self.colormap_range = None
        # self.colormap_is_indicator = False
        # self.colormap_lut = None

    @property
    def shape(self):
        return self.data.shape

    def createErrorVolume(err):
        vol = Volume()
        vol.error = err
        return vol

    def setImmediateDataMode(self, flag):
        pass

    # return size of data in bytes
    def dataSize(self):
        if self.data_header is None:
            return 0
        sz = self.sizes
        # assumes that each data word is 2 bytes
        return 2*sz[0]*sz[1]*sz[2]

    # class function
    def sliceSize(start, stop, step):
        jmi = stop-start
        q = jmi // step
        r = jmi % step
        size = q
        if r != 0:
            size += 1
        return size

    def averageStepSize(self):
        gs = self.gijk_steps
        sizemult = (gs[0]*gs[1]*gs[2])**(1./3.)
        return sizemult

    # Called by project if project's voxel size changes
    def setVoxelSizeUm(self, voxelSizeUm):
        sizemult = self.averageStepSize()
        self.apparentVoxelSize = sizemult*voxelSizeUm 

    # returns a numpy array with min and max corner ijks
    def corners(self):
        xyz0 = np.array(self.gijk_starts, dtype=np.int32)
        dxyz = np.array(self.gijk_steps, dtype=np.int32)
        nxyz = np.array(self.sizes, dtype=np.int32)
        gmin = xyz0
        gmax = xyz0 + dxyz*(nxyz-1)
        gs = np.array((gmin, gmax))
        return gs

    # class function
    # performs an in-place sort of the list
    def sortVolumeList(vols):
        vols.sort(key=lambda v: v.name)

    # project is the project that the nrrd file will be added to
    # tiff_directory is the name of the directory containing the
    # tiff files
    # name is the stem of the output nrrd file 
    # ranges is:
    # [xmin, xmax, xstep], [ymin, ymax, ystep], [zmin, zmax, zstep]
    # (ints not strings)
    # where x and y correspond to positions in the tiff files,
    # and z is the tiff file number
    # these ranges are inclusive, so xmin=0 xmax=5 mean that
    # x values of 0,1,2,3,4,5 will be taken.
    # pattern is the format of the tiff file name, for instance 
    # "%05d.tif"
    # instead of setting pattern, a dictionary of the tiff filenames 
    # { int(z): filename, ...}
    # can be provided to filenames
    # callback, if specified, should take a string as argument, and return 
    # True to continue, False to stop
    # 
    # class function
    def createFromTiffs(project, tiff_directory, name, ranges, pattern, filenamedict=None, callback=None, from_vc_render=False):
        axes = None
        # print("fvcr", from_vc_render)
        if from_vc_render:
            axes = (1,0,2)

        # TODO: make sure 'name' is a valid file name
        # (lower case a-z, numbers, underscore, hyphen, space, dot 
        # (the last 3 not allowed to start or end a file name))
        xrange, yrange, zrange = ranges

        err = ""
        if xrange[0] < 0:
            err = "invalid x start value %d"%xrange[0]
        elif yrange[0] < 0:
            err = "invalid y start value %d"%yrange[0]
        elif xrange[0] >= xrange[1]:
            err = "x start value %d must be less than x end value %d"%(xrange[0],xrange[1])
        elif yrange[0] >= yrange[1]:
            err = "y start value %d must be less than y end value %d"%(yrange[0],yrange[1])
        elif xrange[2] <= 0:
            err = "x step %d must be greater than 0"%xrange[1]
        elif yrange[2] <= 0:
            err = "y step %d must be greater than 0"%yrange[1]
        elif zrange[2] <= 0:
            err = "image step %d must be greater than 0"%zrange[1]
        if err != "":
            print(err)
            return Volume.createErrorVolume(err)

        if pattern == "" and filenamedict is None:
            err = "need to specify either pattern or filenames"
            print(err)
            return Volume.createErrorVolume(err)

        tdir = pathlib.Path(tiff_directory)
        if not tdir.is_dir():
            err = "%s is not a directory"%tdir
            print(err)
            return Volume.createErrorVolume(err)
        oname = name
        if oname[-5:] != '.nrrd':
            oname += '.nrrd'
        ofilefull = project.volumes_path / oname
        if ofilefull.exists():
            err = "%s already exists"%ofilefull
            print(err)
            return Volume.createErrorVolume(err)
        try:
            open(ofilefull, 'wb')
        except Exception as e:
            err = "cannot write to file %s: %s"%(ofilefull, str(e))
            print(err)
            ofilefull.unlink(True)
            return Volume.createErrorVolume(err)
        xsize = Volume.sliceSize(xrange[0], xrange[1]+1, xrange[2])
        ysize = Volume.sliceSize(yrange[0], yrange[1]+1, yrange[2])
        zsize = Volume.sliceSize(zrange[0], zrange[1]+1, zrange[2])
        gb = 1.*xsize*ysize*zsize*2/1000000000
        print("allocating numpy cube, size %.3f Gb"%gb)
        if callback is not None and not callback("Allocating %.1f Gb of memory"%gb):
            ofilefull.unlink(True)
            return Volume.createErrorVolume("Cancelled by user")
        ocube = np.zeros((zsize, ysize, xsize), dtype=np.uint16)
        first_print = True
        for i,z in enumerate(range(zrange[0], zrange[1]+1, zrange[2])):
            if pattern == "":
                if z not in filenamedict:
                    err = "file for image %d is missing"%z
                    print(err)
                    ofilefull.unlink(True)
                    return Volume.createErrorVolume(err)
                fname = filenamedict[z]
            else:
                fname = pattern%z
            imgf = tdir / fname
            # print(fname, imgf)
            if callback is not None and not callback("Reading %s"%fname):
                ofilefull.unlink(True)
                return Volume.createErrorVolume("Cancelled by user")
            iarr = None
            try:
                # note that imread doesn't throw an exception
                # when it cannot find the file, it simply returns
                # None
                iarr = cv2.imread(str(imgf), cv2.IMREAD_UNCHANGED)
            except cv2.error as e:
                err = "could not read file %s: %s"%(imgf, str(e))
                print(err)
                ofilefull.unlink(True)
                return Volume.createErrorVolume(err)
            if iarr is None:
                err = "failed to read file %s"%(imgf)
                print(err)
                ofilefull.unlink(True)
                return Volume.createErrorVolume(err)

            if xrange[1]+1 > iarr.shape[1]:
                err = "max requested x value %d is outside x range %d of image %s"%(xrange[1],iarr.shape[1]-1, fname)
                print(err)
                ofilefull.unlink(True)
                return Volume.createErrorVolume(err)
            if yrange[1]+1 > iarr.shape[0]:
                err = "requested y range %d to %d is outside y range %d of image %s"%(yrange[1], iarr.shape[0]-1, fname)
                ofilefull.unlink(True)
                return Volume.createErrorVolume(err)
            if iarr.dtype == np.uint8:
                if first_print:
                   print("tiff file is unsigned 8 bit, multiplying by 256")
                   first_print = False
                iarr = iarr.astype(np.uint16)
                iarr *= 256
            ocube[i] = np.copy(
                    iarr[yrange[0]:yrange[1]+1:yrange[2], 
                        xrange[0]:xrange[1]+1:xrange[2]])

        print("\nbeginning stack")
        if callback is not None and not callback("Stacking images"):
            ofilefull.unlink(True)
            return Volume.createErrorVolume("Cancelled by user")
        timestamp = Utils.timestamp()
        range0 = [xrange[0], yrange[0], zrange[0]]
        drange = [xrange[2], yrange[2], zrange[2]]
        if axes is not None:
            range0 = (range0[0], range0[2], range0[1])
            drange = (drange[0], drange[2], drange[1])
        header = {
                "khartes_xyz_starts": "%d %d %d"%(range0[0], range0[1], range0[2]),
                "khartes_xyz_steps": "%d %d %d"%(drange[0], drange[1], drange[2]),
                "khartes_version": "1.0",
                "khartes_created": timestamp,
                "khartes_modified": timestamp,
                "khartes_from_vc_render": from_vc_render,
                "khartes_uses_overlay_colormap": False,
                # turns off the default gzip compression (scroll images
                # don't compress well, so compression only slows down
                # the I/O speed)
                "encoding": "raw",
                }
        print("beginning transpose")
        if callback is not None and not callback("Beginning transpose"):
            ofilefull.unlink(True)
            return Volume.createErrorVolume("Cancelled by user")
        if axes is not None:
            # the copy() uses more memory, but makes the write
            # much faster, because it reorders the array.  
            # Note that this is called only
            # for transposed data (data generated by vc_layers)
            ocube = np.transpose(ocube, axes=axes).copy()
        print("beginning write to %s"%ofilefull)
        if callback is not None and not callback("Beginning write to %s"%ofilefull):
            return Volume.createErrorVolume("Cancelled by user")
        nrrd.write(str(ofilefull), ocube, header, index_order='C')
        # nrrd.write(str(ofilefull), tocube, header)
        print("file %s saved"%ofilefull)
        callback("Loading volume from %s"%ofilefull)
        volume = Volume.loadNRRD(ofilefull)
        project.addVolume(volume)
        
        return volume

    def loadData(self, project_view):
        if self.data is not None:
            return
        print("reading data from",self.path,"for",self.name)
        # need to call nrrd.read rather than nrrd.read_data,
        # because nrrd.read_data has complicated prerequisites
        data, data_header = nrrd.read(str(self.path), index_order='C')
        print("finished reading")
        self.data = data
        self.createTransposedData()
        self.active_project_views.add(project_view)
        # self.setDirection(0)
        print(self.data.shape, self.trdatas[0].shape, self.trdatas[1].shape)

    def unloadData(self, project_view):
        volume_view = project_view.volumes[self]
        self.active_project_views.discard(project_view)
        l = len(self.active_project_views)
        if l > 0:
            print("unloadData: still %d project views using this volume"%l)
            return
        print("unloading data for", self.name)
        # These are all needed in order to remove all
        # references to self.data, which then allows the
        # memory to be released.
        self.data = None
        self.trdatas = None
        self.trdata = None
        volume_view.trdata = None

    def loadNRRD(filename, missing_allowed=False):
        try:
            print("reading header for",filename)
            data_header = nrrd.read_header(str(filename))
            print("finished reading")
            gijk_starts = [0,0,0]
            gijk_steps = [1,1,1]
            gijk_sizes = [0,0,0]
            version = 0.0
            if "khartes_version" in data_header:
                vstr = data_header["khartes_version"]
                try:
                    version = float(vstr)
                except:
                    pass
            if "khartes_xyz_starts" in data_header:
                # x, y, imageNumber
                xyzstr = data_header['khartes_xyz_starts']
                try:
                    gijk_starts = tuple(
                        int(x) for x in xyzstr.split())
                    print("gijk_starts", gijk_starts)
                except:
                    err="nrrd file could not parse khartes_xyz_starts string '%s'"%xyzstr
                    print(err)
                    return Volume.createErrorVolume(err)
            elif not missing_allowed:
                err="nrrd file %s is missing header 'khartes_xyz_starts'"%filename
                print(err)
                return Volume.createErrorVolume(err)
            if "khartes_xyz_steps" in data_header:
                xyzstr = data_header['khartes_xyz_steps']
                try:
                    gijk_steps = tuple(
                        int(x) for x in xyzstr.split())
                except:
                    err="nrrd file could not parse khartes_xyz_steps string '%s'"%xyzstr
                    print(err)
                    return Volume.createErrorVolume(err)
            elif not missing_allowed:
                err="nrrd file %s is missing header 'khartes_xyz_steps'"%filename
                print(err)
                return Volume.createErrorVolume(err)
            if "sizes" in data_header:
                sizes = data_header['sizes']
            else:
                err="nrrd file %s is missing header 'sizes'"%filename
                print(err)
                return Volume.createErrorVolume(err)
            created = data_header.get("khartes_created", "")
            modified = data_header.get("khartes_modified", "")
            from_vc_render_str = data_header.get("khartes_from_vc_render", "False")
            from_vc_render = False
            if from_vc_render_str == "True":
                from_vc_render = True

            uses_overlay_colormap_str = data_header.get("khartes_uses_overlay_colormap", "False")
            uses_overlay_colormap = False
            if uses_overlay_colormap_str == "True":
                uses_overlay_colormap = True

        except Exception as e:
            err = "Failed to read nrrd file %s: %s"%(filename,e)
            print(err)
            return Volume.createErrorVolume(err)
        volume = Volume()
        volume.data_header = data_header
        volume.gijk_starts = gijk_starts
        volume.gijk_steps = gijk_steps
        volume.version = version
        volume.created = created
        volume.modified = modified
        volume.from_vc_render = from_vc_render
        volume.uses_overlay_colormap = uses_overlay_colormap
        '''
        if uses_overlay_colormap:
            volume.colormap_range = None
            volume.colormap_name = "kh_encoded_555"
            volume.colormap_is_indicator = True
        volume.setColormap(force_set=True)
        '''
        if uses_overlay_colormap:
            volume.can_modify_colormap = False
        volume.valid = True
        volume.path = filename
        volume.name = filename.stem
        volume.data = None
        # convert np.int32 to int
        volume.sizes = tuple(int(sz) for sz in sizes)
        # volume.dtype_str = data_header["type"]
        dtype_str = data_header["type"]
        volume.dtype = np.dtype(dtype_str)
        print(version, created, modified, volume.sizes)
        return volume

    def createTransposedData(self):
        self.trdatas = []
        # self.trdatas.append(self.data.transpose(2,0,1))
        # self.trdatas.append(self.data.transpose(1,0,2))
        self.trdatas.append(TransposedDataView(self.data, 0))
        self.trdatas.append(TransposedDataView(self.data, 1))

    def ijkToTransposedIjk(self, ijk, direction):
        i,j,k = ijk
        if direction == 0:
            return (j,k,i)
        else:
            return (i,k,j)

    def transposedIjkToIjk(self, ijkt, direction):
        it,jt,kt = ijkt
        if direction == 0:
            return (kt,it,jt)
        else:
            return (it,kt,jt)

    def transposedIjkToGlobalPosition(self, ijkt, direction):
        (i,j,k) = self.transposedIjkToIjk(ijkt, direction)
        steps = self.gijk_steps
        zeros = self.gijk_starts
        gi = zeros[0]+i*steps[0]
        gj = zeros[1]+j*steps[1]
        gk = zeros[2]+k*steps[2]
        return (gi, gj, gk)

    # gpoints is an array of ints.  Each row consists of gx, gy, gz
    # where gx and gy correspond to x and y on the tif image
    # and gz is the number of the image
    def globalPositionsToTransposedIjks(self, gpoints, direction):
        g0 = np.array(self.gijk_starts)
        dg = np.array(self.gijk_steps)
        ijks = (gpoints-g0)/dg
        if direction == 0:
            tijks = ijks[:,(1,2,0)]
        else:
            tijks = ijks[:,(0,2,1)]
        return tijks

    def globalPositionToTransposedIjk(self, gpoint, direction):
        g0 = self.gijk_starts
        dg = self.gijk_steps
        ijk = [(gpoint[i]-g0[i])/dg[i] for i in range(3)]
        if direction == 0:
            # tijk = ijk[(1,2,0)]
            tijk = (ijk[1],ijk[2],ijk[0])
        else:
            tijk = (ijk[0],ijk[2],ijk[1])
        return tijk

    # class function
    def globalIjksToTransposedGlobalIjks(gijks, direction):
        if direction == 0:
            tijks = gijks[:,(1,2,0)]
        else:
            tijks = gijks[:,(0,2,1)]
        return tijks

    # class function
    def transposedGlobalIjksToGlobalIjks(tijks, direction):
        if direction == 0:
            gijks = tijks[:,(2,0,1)]
        else:
            gijks = tijks[:,(0,2,1)]
        return gijks

    def transposedIjksToGlobalPositions(self, ijkts, direction):
        if direction == 0:
            ijks = ijkts[:,(2,0,1)]
        else:
            ijks = ijkts[:,(0,2,1)]
        g0 = np.array(self.gijk_starts)
        dg = np.array(self.gijk_steps)
        gijks = dg*ijks + g0
        return gijks

    # returns range as [[imin,imax], [jmin,jmax], [kmin,kmax]]
    def getGlobalRanges(self):
        arr = []
        steps = self.gijk_steps
        zeros = self.gijk_starts
        for i in range(3):
            mn = zeros[i]
            n = self.data.shape[2-i]
            mx = mn+(n-1)*steps[i]
            arr.append([mn, mx])
        return arr

    def globalAxisFromTransposedAxis(self, axis, direction):
        if direction == 0:
            return (axis+1)%3
        else:
            return (0,2,1)[axis]

    def getSliceInRange(self, data, islice, jslice, k, axis):
        i, j = self.ijIndexesInPlaneOfSlice(axis)
        slices = [0]*3
        slices[axis] = k
        slices[i] = islice
        slices[j] = jslice
        result = data[slices[2],slices[1],slices[0],:]
        return result

    def getSliceShape(self, axis, zarr_max_width, direction):
        # zarr_max_width will be ignored
        shape = self.trdatas[direction].shape
        if axis == 2: # depth
            return shape[1],shape[2]
        elif axis == 1: # xline
            return shape[0],shape[2]
        else: # inline
            return shape[0],shape[1]

    def paintSlice(self, out, axis, ijkt, zoom, zarr_max_width, direction):
        # zarr_max_width is ignored here; it only applies to zarr volumes
        data = self.trdatas[direction]
        z = zoom
        it,jt,kt = ijkt
        wh,ww,wd = out.shape
        whw = ww//2
        whh = wh//2
        il, jl = self.ijIndexesInPlaneOfSlice(axis)
        fi, fj, fk = ijkt[il], ijkt[jl], ijkt[axis]
        # slice width, height
        sw = data.shape[2-il]
        sh = data.shape[2-jl]
        sd = data.shape[2-axis]
        if fk < 0 or fk >= sd:
            return True
        '''
        test = self.getSliceInRange(
                slice(0,None), slice(0,None), 0, 
                axis, direction)
        print(axis, data.shape, il, jl, sw, sh, test.shape)
        '''
        # print("sw,sh",z,il,jl,fi,fj,sw,sh)
        zsw = max(int(z*sw), 1)
        zsh = max(int(z*sh), 1)

        # all coordinates below are in drawing window coordinates,
        # unless specified otherwise
        # location of upper left corner of data slice:
        ax1 = int(whw-z*fi)
        ay1 = int(whh-z*fj)
        # location of lower right corner of data slice:
        ax2 = ax1+zsw
        ay2 = ay1+zsh
        # print(z,ax1,ay1,ax2,ay2)
        # locations of upper left and lower right corners of drawing window
        bx1 = 0
        by1 = 0
        bx2 = ww
        by2 = wh
        ri = Utils.rectIntersection(
                ((ax1,ay1),(ax2,ay2)), ((bx1,by1),(bx2,by2)))
        if ri is not None:
            # upper left and lower right corners of intersected rectangle
            (x1,y1),(x2,y2) = ri
            # corners of windowed data slice, in
            # data slice coordinates
            x1s = int((x1-ax1)/z)
            y1s = int((y1-ay1)/z)
            x2s = int((x2-ax1)/z)
            y2s = int((y2-ay1)/z)
            # print(sw,sh,ww,wh)
            # print(x1,y1,x2,y2)
            # print(x1s,y1s,x2s,y2s)
            slc = self.getSliceInRange(data,
                    slice(x1s,x2s), slice(y1s,y2s), ijkt[axis], 
                    axis)
            # print(slc.shape)
            # resize windowed data slice to its size in drawing
            # window coordinates
            if self.uses_overlay_colormap:
                zslc = cv2.resize(slc, (x2-x1, y2-y1), interpolation=cv2.INTER_NEAREST)
            else:
                zslc = cv2.resize(slc, (x2-x1, y2-y1), interpolation=cv2.INTER_AREA)

            # TODO:
            zslc = zslc[:,:,np.newaxis]
            # paste resized data slice into the intersection window
            # in the drawing window
            out[y1:y2, x1:x2, :] = zslc
            
        return True

    def ijIndexesInPlaneOfSlice(self, axis):
        return ((1,2), (0,2), (0,1))[axis]

    def globalSlicePositionAlongAxis(self, axis, ijkt, direction):
        gi,gj,gk = self.transposedIjkToGlobalPosition(ijkt, direction)
        return (gi, gj, gk)[axis]

    # call after direction is set
    # it, jt, kt are ijk in transposed grid
    # it (fast, axis 0) is inline coord
    # jt (med, axis 1) is xline coord
    # kt (slow, axis 2) is depth coord
    # trdata is laid out in C style, so 
    # value at it,ij,ik is indexed trdata[kt,jt,it]
    def getSlices(self, ijkt, direction):
        #print(f"Slicing at {ijkt}")
        depth = self.getSlice(2, ijkt, direction)
        xline = self.getSlice(1, ijkt, direction)
        inline = self.getSlice(0, ijkt, direction)

        return (depth, xline, inline)

    def getSliceShapes(self, zarr_max_width, direction):
        depth = self.getSliceShape(2, zarr_max_width, direction)
        xline = self.getSliceShape(1, zarr_max_width, direction)
        inline = self.getSliceShape(0, zarr_max_width, direction)
        return (depth, xline, inline)

    def getSliceBounds(self, axis, ijkt, zarr_max_width, direction):
        # zarr_max_width is ignored
        idxi, idxj = self.ijIndexesInPlaneOfSlice(axis)
        shape = self.trdatas[direction].shape
        ni = shape[2-idxi]
        nj = shape[2-idxj]
        return ((0,0),(ni,nj))
