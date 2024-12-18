import json
import time
import math
# from queue import LifoQueue
from collections import deque

import numpy as np
import cv2
import rectpack
from scipy.spatial import Delaunay
from scipy.spatial.qhull import QhullError
from scipy.interpolate import (
        LinearNDInterpolator, 
        NearestNDInterpolator, 
        CloughTocher2DInterpolator,
        RegularGridInterpolator,
        )
from scipy.interpolate import CubicSpline
from utils import Utils
from volume import Volume
from base_fragment import BaseFragment, BaseFragmentView
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

class FragmentsModel(QtCore.QAbstractTableModel):
    def __init__(self, project_view, main_window):
        super(FragmentsModel, self).__init__()
        # note that self.project_view should not be
        # changed after initialization; instead, a new
        # instance of VolumesModel should be created
        # and attached to the QTableView
        self.project_view = project_view
        self.main_window = main_window

    columns = [
            "Active",
            "Visible",
            "Hide\nMesh",
            "Name",
            "Color",
            "Type",  # Add new column
            "Dir",
            "Pts",
            "cm^2"
            ]
    
    ctips = [
            "Select which fragment is active;\nclick box to select.\nNote that you can only select fragments\nwhich have the same direction (orientation)\nas the current volume view",
            "Select which fragments are visible;\nclick box to select",
            "Select which fragments have their mesh hidden;\nclick box to select",
            "Name of the fragment; click to edit",
            "Color of the fragment; click to edit",
            "Type of fragment (2.5D or 3D)",  # Add new tooltip
            "Direction (orientation) of the fragment",
            "Number of points currently in fragment",
            "Fragment area in square centimeters"
            ]

    # Add these static methods
    @staticmethod
    def columnIndex(name):
        return FragmentsModel.columns.index(name)

    @staticmethod 
    def columnIndices(names):
        inds = []
        for name in names:
            inds.append(FragmentsModel.columnIndex(name))
        return inds

    def flags(self, index):
        col = index.column()
        oflags = super(FragmentsModel, self).flags(index)
        if col in self.columnIndices(["Active", "Visible", "Hide\nMesh"]):
            nflags = Qt.ItemNeverHasChildren
            nflags |= Qt.ItemIsUserCheckable
            nflags |= Qt.ItemIsEnabled
            return nflags
        elif col == self.columnIndex("Name"):
            nflags = Qt.ItemNeverHasChildren
            nflags |= Qt.ItemIsEnabled
            nflags |= Qt.ItemIsEditable
            return nflags
        else:
            return Qt.ItemNeverHasChildren|Qt.ItemIsEnabled

    def headerData(self, section, orientation, role):
        if orientation != Qt.Horizontal:
            return
        
        if role == Qt.DisplayRole:
            if section == 0:
                # print("HD", self.rowCount())
                table = self.main_window.fragments_table
                # make sure the color button in column 3 is always open
                # (so no double-clicking required)
                for i in range(self.rowCount()):
                    index = self.createIndex(i, self.columnIndex("Color"))
                    table.openPersistentEditor(index)

            return FragmentsModel.columns[section]
        elif role == Qt.ToolTipRole:
            return FragmentsModel.ctips[section]

    def columnCount(self, parent=None):
        return len(FragmentsModel.columns)

    def rowCount(self, parent=None):
        if self.project_view is None:
            return 0
        fragments = self.project_view.fragments
        # print("row count", len(fragments.keys()))
        return len(fragments.keys())

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
        return None

    def dataCheckStateRole(self, index, role):
        column = index.column()
        row = index.row()
        fragments = self.project_view.fragments
        fragment = list(fragments.keys())[row]
        fragment_view = fragments[fragment]
        if column == self.columnIndex("Active"):
            if fragment_view.active:
                return Qt.Checked
            else:
                return Qt.Unchecked
        if column == self.columnIndex("Visible"):
            if fragment_view.visible:
                return Qt.Checked
            else:
                return Qt.Unchecked
        if column == self.columnIndex("Hide\nMesh"):
            # Note that column is "Hide\nMesh", but
            # internal variable is mesh_visible
            if fragment_view.mesh_visible:
                return Qt.Unchecked
            else:
                return Qt.Checked

    def dataAlignmentRole(self, index, role):
        return Qt.AlignVCenter + Qt.AlignRight

    def dataBackgroundRole(self, index, role):
        row = index.row()
        fragments = self.project_view.fragments
        fragment = list(fragments.keys())[row]
        fragment_view = fragments[fragment]
        if self.project_view.mainActiveVisibleFragmentView() == fragment_view:
            # return QtGui.QColor('beige')
            return QtGui.QColor(self.main_window.highlightedBackgroundColor())

    def dataDisplayRole(self, index, role):
        row = index.row()
        column = index.column()
        fragments = self.project_view.fragments
        fragment = list(fragments.keys())[row]
        fragment_view = fragments[fragment]
        
        if column == self.columnIndex("Name"):
            return fragment.name
        elif column == self.columnIndex("Color"):
            return fragment.color.name()
        elif column == self.columnIndex("Dir"):
            return ('X','Y')[fragment.direction]
        elif column == self.columnIndex("Pts"):
            return len(fragment.gpoints)
        elif column == self.columnIndex("cm^2"):
            return "%.4f"%fragment_view.sqcm
        elif column == self.columnIndex("Type"):
            return fragment.getType()
        else:
            return None

    def setData(self, index, value, role):
        row = index.row()
        column = index.column()
        fragments = self.project_view.fragments
        fragment = list(fragments.keys())[row]
        fragment_view = fragments[fragment]

        if role == Qt.CheckStateRole:
            cv = Qt.CheckState(value)
            if column == self.columnIndex("Active"):
                exclusive = True
                if ((self.main_window.app.keyboardModifiers() & Qt.ControlModifier) 
                   or 
                   len(self.main_window.project_view.activeFragmentViews(unaligned_ok=True)) > 1):
                    exclusive = False
                self.main_window.setFragmentActive(fragment, cv==Qt.Checked, exclusive)
                return True
            elif column == self.columnIndex("Visible"):
                self.main_window.setFragmentVisibility(fragment, cv==Qt.Checked)
                return True
            elif column == self.columnIndex("Hide\nMesh"):
                print("hide", fragment, cv==Qt.Unchecked)
                print("Hide column index:", self.columnIndex("Hide\nMesh"))
                print("Current column:", column)
                print("Setting mesh visibility to:", cv==Qt.Unchecked)
                self.main_window.setFragmentMeshVisibility(fragment, cv==Qt.Unchecked)
                # self.dataChanged.emit(index, index, [Qt.CheckStateRole])
                return True

        elif role == Qt.EditRole:
            if column == self.columnIndex("Name"):
                name = value
                if name != "":
                    self.main_window.renameFragment(fragment, name)
            elif column == self.columnIndex("Color"):
                self.main_window.setFragmentColor(fragment, value)

        return False

    def scrollToRow(self, row):
        index = self.createIndex(row, 0)
        table = self.main_window.fragments_table
        table.scrollTo(index)

    def scrollToEnd(self):
        row = self.rowCount()-1
        if row < 0:
            return
        self.scrollToRow(row)


# note that FragmentView is defined after Fragment
class Fragment(BaseFragment):

    # class variable
    min_roundness = .1

    def __init__(self, name, direction):
        super(Fragment, self).__init__(name)
        self.direction = direction
        self.params = {}
        # fragment points in global coordinates
        self.gpoints = np.zeros((0,3), dtype=np.float32)

        # History of gpoints, for undo functionality
        # self.gpoints_history : LifoQueue = LifoQueue(50)
        self.gpoints_history = deque(maxlen=50)
        self.type = BaseFragment.Type.FRAGMENT

    def createView(self, project_view):
        return FragmentView(project_view, self)

    def createCopy(self, name):
        frag = Fragment(name, self.direction)
        frag.setColor(self.color, no_notify=True)
        frag.gpoints = np.copy(self.gpoints)
        frag.valid = True
        return frag

    def toDict(self):
        info = {}
        info['name'] = self.name
        info['created'] = self.created
        info['modified'] = self.modified
        info['direction'] = self.direction
        info['color'] = self.color.name()
        info['params'] = self.params
        info['type'] = self.type.value if self.type else Fragment.Type.FRAGMENT.value  # Save fragment type
        info['gpoints'] = self.gpoints.tolist()
        if self.params.get('echo', '') != '':
            info['gpoints'] = []
        return info


    def save(self, path):
        info = self.toDict()
        # print(info)
        info_txt = json.dumps(info, indent=4)
        file = path / (self.name + ".json")
        print("writing to",file)
        file.write_text(info_txt, encoding="utf8")

    # class function
    def saveList(frags, path, stem):
        infos = []
        for frag in frags:
            if not hasattr(frag, "toDict"):
                continue
            info = frag.toDict()
            infos.append(info)
        info_txt = json.dumps(infos, indent=4)
        file = path / (stem + ".json")
        print("writing to",file)
        file.write_text(info_txt, encoding="utf8")

    def createErrorFragment(err):
        frag = Fragment("", -1)
        frag.error = err
        return frag

    # class function
    def fragFromDict(info):
        for attr in ['name', 'direction', 'gpoints']:
            if attr not in info:
                err = "file missing parameter %s"%(attr)
                print(err)
                return Fragment.createErrorFragment(err)

        if 'color' in info:
            color = QColor(info['color'])
        else:
            color = Utils.getNextColor()
        name = info['name']
        direction = info['direction']
        gpoints = info['gpoints']
        
        # Create correct fragment type based on saved type
        frag_type = info.get('type', BaseFragment.Type.FRAGMENT.value)
        if frag_type == BaseFragment.Type.UMBILICUS.value:
            from umbilicus_fragment import UmbilicusFragment
            frag = UmbilicusFragment(name, direction)
        else:
            frag = Fragment(name, direction)
            
        frag.setColor(color, no_notify=True)
        frag.valid = True
        if len(gpoints) > 0:
            frag.gpoints = np.array(gpoints, dtype=np.float32)
        if 'params' in info:
            frag.params = info['params']
        else:
            frag.params = {}
        if 'created' in info:
            frag.created = info['created']
        else:
            time.sleep(.1)
            frag.created = Utils.timestamp()
        if 'modified' in info:
            frag.modified = info['modified']
        else:
            frag.modified = frag.created

        return frag

    @staticmethod
    def pointThreeAxes(pt_index, xyzpts, uvpts, trgls):
        # print("PTA")
        # TODO: make this act like a zsurf
        # return BaseFragment.pointThreeAxes(pt_index, xyzpts, uvpts, trgls)
        return np.array([[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])

    # TODO: need "created" and "modified" timestamps
    # class function
    def load(json_file):
        try:
            json_txt = json_file.read_text(encoding="utf8")
        except:
            err = "Could not read file %s"%json_file
            print(err)
            return [Fragment.createErrorFragment(err)]

        try:
            infos = json.loads(json_txt)
        except:
            err = "Could not parse file %s"%json_file
            print(err)
            return [Fragment.createErrorFragment(err)]

        if not isinstance(infos, list):
            infos = [infos]

        frags = []
        for info in infos:
            frag = Fragment.fragFromDict(info)
            if not frag.valid:
                return [frag]
            frags.append(frag)
        return frags

    # class function
    # performs an in-place sort of the list
    def sortFragmentList(frags):
        frags.sort(key=lambda f: f.name)

    def minRoundness(self):
        return Fragment.min_roundness

    def badTrglsBySkinniness(self, tri, min_roundness):
        simps = tri.simplices
        # 2D coordinates
        verts = tri.points
        v0 = verts[simps[:,0]]
        v1 = verts[simps[:,1]]
        v2 = verts[simps[:,2]]
        v01 = v1-v0
        v02 = v2-v0
        v12 = v2-v1
        area = abs(.5*(v01[:,0]*v02[:,1] - v01[:,1]*v02[:,0]))
        
        l01 = np.sqrt((v01*v01).sum(1))
        l02 = np.sqrt((v02*v02).sum(1))
        l12 = np.sqrt((v12*v12).sum(1))

        circumference = l01+l02+l12
        pmax = math.sqrt(.25*math.sqrt(3.))/3

        roundness = np.sqrt(area)/(circumference*pmax)

        bads = np.where(roundness < self.minRoundness())[0]
        return bads

    def badTrglsByMaxAngle(self, tri):
        simps = tri.simplices
        verts = tri.points
        v0 = verts[simps[:,0]]
        v1 = verts[simps[:,1]]
        v2 = verts[simps[:,2]]
        v01 = v1-v0
        v02 = v2-v0
        v12 = v2-v1
        l01 = np.sqrt((v01*v01).sum(1))
        l02 = np.sqrt((v02*v02).sum(1))
        l12 = np.sqrt((v12*v12).sum(1))
        d12 = (v01*v02).sum(1)/(l01*l02)
        d01 = (v02*v12).sum(1)/(l02*l12)
        d02 = -(v01*v12).sum(1)/(l01*l12)
        ds = np.array((d01,d02,d12)).transpose()
        # print("ds shape", ds.shape)
        dmax = np.amax(ds, axis=1)
        dmin = np.amin(ds, axis=1)
        # print("dmax shape", dmax.shape)
        mind = -.95
        mind = -.99
        bads = np.where(dmin < mind)[0]
        return bads

    def badTrglsByNormal(self, tri, pts):
        simps = tri.simplices
        v0 = pts[simps[:,0]]
        v1 = pts[simps[:,1]]
        v2 = pts[simps[:,2]]
        v01 = v1-v0
        v02 = v2-v0
        l01 = np.sqrt((v01*v01).sum(1))
        l02 = np.sqrt((v02*v02).sum(1))
        norm = np.cross(v01, v02)/(l01*l02).reshape(-1,1)
        # print("norm",v01.shape, v02.shape, norm.shape)
        # print(norm[0:10])
        bads = np.where(np.abs(norm[:,2]) < .1)
        # bads = np.where(np.abs(norm[:,2]) < 0)
        return bads

    # given array of indices of "bad" trgls, return a subset of the list,
    # consisting of bad trgls that are (recursively) on the border
    def badBorderTrgls(self, tri, bads):
        # print("bads", bads)
        badbool = np.zeros((len(tri.simplices),), dtype=np.bool8)
        badbool[bads] = True
        borderlist = np.array((-1,), dtype=np.int32)
        lbl = len(borderlist)
        while True:
            borderbool = np.isin(tri.neighbors, borderlist).any(axis=1)
            badbordertrgls = np.where(np.logical_and(borderbool, badbool))[0]
            # print("bad on border", len(badbordertrgls))
            borderlist = np.unique(np.append(borderlist, badbordertrgls))
            newlbl = len(borderlist)
            if newlbl == lbl:
                break
            lbl = newlbl
        return badbordertrgls

    # Using self.gpoints, create new points in the
    # global coordinate system to infill the grid at the given
    # spacing.  Infill points will be omitted wherever there
    # is an existing grid point nearby.  Returns the new gpoints.
    def createInfillPoints(self, infill):
        direction = self.direction
        gijks = self.gpoints
        # ngijks = np.zeros((0,3), dtype=np.int32)
        ngijks = np.zeros((0,3), dtype=np.float32)
        if infill <= 0:
            return ngijks
        tgijks = Volume.globalIjksToTransposedGlobalIjks(gijks, direction)

        print("tgijks", tgijks.shape, tgijks.dtype)
        if tgijks.shape == 0:
            return ngijks
        mini = np.amin(tgijks[:,0])
        maxi = np.amax(tgijks[:,0])
        minj = np.amin(tgijks[:,1])
        maxj = np.amax(tgijks[:,1])
        print("minmax", mini, maxi, minj, maxj)
        minid = mini/infill
        maxid = maxi/infill
        minjd = minj/infill
        maxjd = maxj/infill
        
        id0 = math.floor(minid)
        idm = math.floor(maxid)
        if idm != maxid:
            idm += 1
        idn = idm-id0+1

        jd0 = math.floor(minjd)
        jdm = math.floor(maxjd)
        if jdm != maxjd:
            jdm += 1
        jdn = jdm-jd0+1
        print("id,jd", id0, idn, jd0, jdn)

        # create an array to hold the coordinates of the infill points
        sid = np.indices((jdn, idn))
        print("sid", idn, jdn, sid.shape, sid.dtype)
        # add a flag layer to indicate whether an existing gpoint
        # is close to one of the proposed infill points
        si = np.append(sid, np.zeros((1, jdn, idn), dtype=sid.dtype), axis=0)
        # set the coordinates (in the transposed global frame) of
        # the infill points
        # notice si[0] corresponds to j and si[0] to i
        si[1] = np.rint((si[1]+id0)*infill+infill/2).astype(si.dtype)
        si[0] = np.rint((si[0]+jd0)*infill+infill/2).astype(si.dtype)
        # calculate the position, in the si array, of the
        # existing transposed gpoints
        itgijks0 = np.int32(np.floor(tgijks[:,0]/infill - id0))
        itgijks1 = np.int32(np.floor(tgijks[:,1]/infill - jd0))
        # set the flag wherever there is an existing point
        si[2,itgijks1,itgijks0] = 1

        # print("si corners", si[:,0,0], si[:,-1,-1])
        # sum should equal the number of gpoints (but may be
        # smaller if more than one gpoint near a single infill point)
        # print("sum", np.sum(si[2]))
        # sib is a boolean of all the infill points that are not near an
        # existing gpoint
        sib = si[2,:,:] == 0
        # print("si sib",si.shape, sib.shape)

        # filter si by sib
        si = si[:2, sib]
        # print("si",si.shape)
        # don't need the infill point in an array any more; flatten them
        # notice si[0] corresponds to j and si[0] to i
        newtis = si[1].flatten()
        newtjs = si[0].flatten()

        newtijs = np.array((newtis, newtjs)).transpose()
        # print("newtijs", newtijs.shape)

        try:
            # triangulate the original gpoints
            tri = Delaunay(tgijks[:,0:2])
        except Exception as err:
            err = str(err).splitlines()[0]
            print("createInfillPoints triangulation error: %s"%err)
            return ngijks

        # bads = self.badBorderTrgls(tri, self.badTrglsByNormal(tri, tgijks))
        bads = self.badBorderTrgls(tri, self.badTrglsBySkinniness(tri, self.minRoundness()))
        badlist = bads.tolist()

        interp = CloughTocher2DInterpolator(tri, tgijks[:,2])
        newtks = interp(newtijs)
        simpids = tri.find_simplex(newtijs)
        newtks = np.reshape(newtks, (newtks.shape[0],1))
        # print("newtks", newtks.shape)
        # the list of infill points, in transposed global
        # ijk coordinates
        newtijks = np.append(newtijs, newtks, axis=1)
        print("newtijks with nans", newtijks.shape)
        # eliminate infill points in "bad" simplices
        newtijks = newtijks[~np.isin(simpids, badlist)]
        print("newtijks no bad trgls", newtijks.shape)
        # eliminate infill points where k is nan
        newtijks = newtijks[~np.isnan(newtijks[:,2])]
        print("newtijks no nans", newtijks.shape)
        ngijks = Volume.transposedGlobalIjksToGlobalIjks(newtijks, direction)

        # TODO: shouldn't be hardwired here!
        voxelSizeUm = self.project.voxel_size_um
        meshCount = len(newtijks)
        area_sq_mm_flat = meshCount*voxelSizeUm*voxelSizeUm*infill*infill/1000000
        simps = tri.simplices
        pts = tgijks
        simps = simps[~(np.isin(simps, bads).any(1))]
        v0 = pts[simps[:,0]].astype(np.float64)
        v1 = pts[simps[:,1]].astype(np.float64)
        v2 = pts[simps[:,2]].astype(np.float64)
        v01 = v1-v0
        v02 = v2-v0
        norm = np.cross(v01, v02)
        # print(norm.shape)
        # print((norm*norm).shape)
        normsq = np.sum(norm*norm, axis=1)
        # print(norm.shape, normsq.shape)
        # normsq = normsq[~np.isnan(normsq)]
        # print(normsq[normsq < 0])
        # print(normsq.shape)
        area_sq_mm_trg = np.sum(np.sqrt(normsq))*voxelSizeUm*voxelSizeUm/(2*1000000)
        print("areas", area_sq_mm_flat, area_sq_mm_trg)


        return ngijks

    class ExportFrag:
        def __init__(self, fv, infill):
            frag = fv.fragment
            gpoints = frag.gpoints
            fname = frag.name
            self.err = ""
            self.fv = fv
            self.frag = frag
            self.trgs = []
            self.has_ssurf = False
            if not fv.mesh_visible:
                self.vrts = gpoints
                return
            print(fname,"gpoints before", len(gpoints))
            newgps = frag.createInfillPoints(infill)
            gpoints = np.append(gpoints, newgps, axis=0)
            print(fname,"gpoints after", len(gpoints))
            self.vrts = gpoints
            tgps = Volume.globalIjksToTransposedGlobalIjks(gpoints, frag.direction)
            try:
                # triangulate the new gpoints
                tri = Delaunay(tgps[:,0:2])
            # except QhullError as err:
            except Exception as err:
                self.err = "%s triangulation error: %s"%(fname,err)
                self.err = self.err.splitlines()[0]
                print(self.err)
                return

            # bads = frag.badBorderTrgls(tri, frag.badTrglsByNormal(tri, tgps))
            bads = frag.badBorderTrgls(tri, frag.badTrglsBySkinniness(tri, frag.minRoundness()))
            badlist = bads.tolist()
            for i,trg in enumerate(tri.simplices):
                if i in badlist:
                    continue
                self.trgs.append(trg)
            print("all",len(tri.simplices),"good",len(self.trgs))

            fv.createZsurf()
            if fv.zsurf is not None and fv.ssurf is not None:
                self.has_ssurf = True
                self.data_rect = Fragment.ExportFrag.dataBounds(fv.zsurf)
                self.shape = fv.zsurf.shape


        # class function
        # returns (x,y,w,h) of bounding box that contains
        # all the data (data that is not NaN).  
        # w,h = 0 if nothing found.
        # Note that if non-NaN data is found, w and h will be at least 1.
        def dataBounds(arr):
            # True if not nan
            b = ~np.isnan(arr)
            # True if row or col has at least one not-nan
            b0 = np.any(b, axis=0)
            b1 = np.any(b, axis=1)
            b0t = b0.nonzero()[0]
            b1t = b1.nonzero()[0]
            if len(b0t) == 0:
                b0min = -1
                b0max = 0
            else:
                b0min = min(b0t)
                b0max = max(b0t)
            if len(b1t) == 0:
                b1min = -1
                b1max = 0
            else:
                b1min = min(b1t)
                b1max = max(b1t)
    
            x = b0min
            w = b0max-b0min+1
            y = b1min
            h = b1max-b1min+1
            # print(b.shape, b0.shape, len(b0t), len(b0min))
            # print(frag.name, b0min, b0max, b1min, b1max)
            return x,y,w,h

        def addTexture(self, arr):
            if not self.has_ssurf:
                return
            xt,yt = self.tex_orig
            x0,y0 = self.data_rect[:2]
            w,h = self.data_rect[2:]
            x1 = x0+w
            y1 = y0+h
            arr[yt:yt+h,xt:xt+w] = self.fv.ssurf[y0:y1,x0:x1]

        # class function
        def pack(efs):
            packer = rectpack.newPacker(
                    rotation=False, pack_algo=rectpack.MaxRectsBlsf)
            pad = 1
            incount = 0
            for ef in efs:
                if not ef.has_ssurf:
                    continue
                dr = ef.data_rect
                packer.add_rect(dr[2]+2*pad, dr[3]+2*pad)
                incount += 1
            ibin = (20000, 20000)
            packer.add_bin(*ibin)
            packer.pack()
            if len(packer.rect_list()) == 0:
                obin = []
            else:
                obin = packer[0]
            '''
            if incount != len(obin):
                err = "Have %d valid efs but only %d rects in obin"%(incount,len(obin))
                print(err)
                return
            '''

            maxx = 0
            maxy = 0
            used = set()
            for rect in obin:
                (x, y, w, h) = rect.x, rect.y, rect.width, rect.height
                found = False
                for ef in efs:
                    if not ef.has_ssurf:
                        continue
                    if ef in used:
                        continue
                    dr = ef.data_rect
                    if w != dr[2]+2*pad or h != dr[3]+2*pad:
                        continue
                    ef.tex_orig = (x+pad,y+pad)
                    used.add(ef)
                    found = True
                if not found:
                    self.err = "Could not find rect %d %d %d %d in efs"%(x,y,w,d)
                    print(err)
                    return
                mx = x+w
                maxx = max(maxx, mx)
                my = y+h
                maxy = max(maxy, my)
            return (maxx, maxy)
            
            

    def meshExportNeedsInfill(self):
        return True

    # class function
    # takes a list of FragmentView's as input
    # texture is taken from current volume, which may not
    # be full resolution
    def saveListAsObjMesh(fvs, filename, infill, ppm, class_count):
        frags = [fv.fragment for fv in fvs]
        print("slaom", len(frags), filename, infill)
        filename = filename.with_suffix(".obj")
        err = ""

        rects = []

        '''
        # diagnostics only
        for fv in fvs:
            frag = fv.fragment
            if fv.zsurf is None or fv.ssurf is None:
                print("Zsurf or ssurf missing for", frag.name)
                continue
            x,y,w,h = Fragment.ExportFrag.dataBounds(fv.zsurf)
            print(frag.name, x, y, w, h)
        '''


        efs = []
        for fv in fvs:
            ef = Fragment.ExportFrag(fv, infill)
            if ef.err != "":
                print("Fragment",ef.frag.name,"error",ef.err)
                # err += ef.err + '\n'
                # continue
            efs.append(ef)

        if len(efs) == 0:
            err = "No exportable fragments"
            print(err)
            return err

        try:
            of = filename.open("w")
        except Exception as e:
            err = "Could not open %s: %s"%(str(filename), e)
            print(err)
            return err

        mfilename = filename.with_suffix(".mtl")
        print("# khartes .obj file", file=of)
        print("#", file=of)
        print("mtllib %s"%mfilename.name, file=of)
        print("# vertices", file=of)
        for ef in efs:
            fv = ef.fv
            mesh_visible = fv.mesh_visible
            rgb = ef.frag.color.getRgbF()
            r = rgb[0]
            g = rgb[1]
            b = rgb[2]
            vrts = ef.vrts
            if ppm is not None:
                vrts = ppm.layerIjksToScrollIjks(vrts)
            print("# fragment", ef.frag.name, file=of)
            for vrt in vrts:
                if mesh_visible:
                    print("v %.2f %.2f %.2f "%(vrt[0],vrt[1],vrt[2]), file=of)
                else:
                    print("v %.2f %.2f %.2f %.4f %.4f %.4f"%(vrt[0],vrt[1],vrt[2], r, g, b), file=of)

        tex_rect = Fragment.ExportFrag.pack(efs)
        if tex_rect is None:
            err = "Could not pack textures (see console message)"
            print(err)
            return err


        for ef in efs:
            if not ef.has_ssurf:
                continue
            print("  ", ef.frag.name, ef.data_rect, ef.tex_orig)

        print("texture size", tex_rect)
        tw,th = tex_rect
        tfilename = ""
        if tw > 0 and th > 0:
            tex_out = np.zeros((th,tw), dtype=np.uint16)
            for ef in efs:
                ef.addTexture(tex_out)

            tfilename = filename.with_suffix(".tif")
            cv2.imwrite(str(tfilename), tex_out)

        print("# texture vertices", file=of)
        for ef in efs:
            print("# fragment", ef.frag.name, file=of)
            if not ef.has_ssurf:
                for i in range(len(ef.vrts)):
                    print("vt %f %f"%(0.,0.), file=of)
                continue

            x0, y0 = ef.tex_orig
            dx, dy, dw, dh = ef.data_rect
            # for vrt in ef.vrts:
            frag = ef.frag
            fv = ef.fv
            # tgps = Volume.globalIjksToTransposedGlobalIjks(ef.vrts, frag.direction)
            tgps = fv.cur_volume_view.volume.globalPositionsToTransposedIjks(ef.vrts, frag.direction)
            for fpt in tgps:
                # print("v %d %d %d"%(vrt[0],vrt[1],vrt[2]), file=of)
                vx, vy = fpt[0:2]
                tx = (vx+x0-dx)/(tw-1)
                ty = (vy+y0-dy)/(th-1)
                ty = 1.-ty
                print("vt %f %f"%(tx, ty), file=of)

        print("# trgls", file=of)
        i0 = 1
        for i,ef in enumerate(efs):
            print("# fragment", ef.frag.name, file=of)
            print("usemtl frag%d"%i, file=of)
            for trg in ef.trgs:
                v0 = trg[0]+i0
                v1 = trg[1]+i0
                v2 = trg[2]+i0
                print("f %d/%d %d/%d %d/%d"%(v0,v0,v1,v1,v2,v2), file=of)
            i0 += len(ef.vrts)

        try:
            ofm = mfilename.open("w")
        except Exception as e:
            err = "Could not open %s: %s"%(str(mfilename), e)
            print(err)
            return err

        for i,ef in enumerate(efs):
            frag = ef.frag
            rgba = frag.color.getRgbF()
            print("newmtl frag%d"%i, file=ofm)
            print("Ka %f %f %f"%(rgba[0],rgba[1],rgba[2]), file=ofm)
            print("Kd %f %f %f"%(rgba[0],rgba[1],rgba[2]), file=ofm)
            print("Ks 0.0 0.0 0.0", file=ofm)
            print("illum 2", file=ofm)
            print("d 1.0", file=ofm)
            if tfilename != "":
                print("map_Kd %s"%tfilename.name, file=ofm)

        jfilename = filename.with_suffix(".json")
        jdict = {}
        for ef in efs:
            frag = ef.frag
            fv = ef.fv
            fdict = {}
            fdict["name"] = frag.name
            fdict["area_sq_cm"] = fv.sqcm
            fdict["n_vrts"] = len(ef.vrts)
            fdict["n_trgls"] = len(ef.trgs)
            jdict[frag.name] = fdict
        info_txt = json.dumps(jdict, indent=4)
        try:
            ofj = jfilename.open("w")
            print(info_txt, file=ofj)
        except Exception as e:
            err = "Could not open %s: %s"%(str(jfilename), e)
            print(err)
            # return err

        return err


class FragmentView(BaseFragmentView):

    # class variables
    # general rule on class variables: they should only be
    # used if the only way to change them is through the dev-tools UI
    use_linear_interpolation = True
    hide_skinny_triangles = False

    def __init__(self, project_view, fragment):
        super(FragmentView, self).__init__(project_view, fragment)
        self.tri = None
        self.line = None
        self.lineAxis = -1
        self.lineAxisPosition = 0
        self.zsurf = None
        self.prevZslice = -1
        self.prevZslicePts = None
        self.ssurf = None
        self.nearbyNode = -1
        self.live_zsurf_update = True
        # gpoints converted to ijk coordinates relative
        # to current volume, using trijk based on 
        # fragment's direction
        self.fpoints = np.zeros((0,4), dtype=np.float32)
        self.oldzs = None
        self.oldtri = None
        # same as above, but trijk based on cur_volume_view's 
        # direction
        self.vpoints = np.zeros((0,4), dtype=np.float32)

    def allowAutoExtrapolation(self):
        return True

    def allowAutoInterpolation(self):
        return True

    def calculateSqCm(self):
        # project_view is None if self.fragment is a working fragment
        # of a TrglFragment
        if self.tri is None or self.project_view is None:
            self.sqcm = 0.
            return 0.
        pts = self.fragment.gpoints
        simps = self.tri.simplices
        voxel_size_um = self.project_view.project.voxel_size_um
        sqcm = BaseFragment.calculateSqCm(pts, simps, voxel_size_um)
        self.sqcm = sqcm

    # This version moves the points in the old way (along the axes)
    def localStAxesHide(self, pt_index):
        axes = np.array([[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
        if self.fragment.direction == 0:
            axes = axes[(2,0,1), :]
        else:
            axes = axes[(0,2,1), :]
        return axes

    # This version moves the points along the normal and the tangent plane
    def localStAxes(self, pt_index):
        axes = super(FragmentView, self).localStAxes(pt_index)
        if axes is None:
            return axes
        if self.cur_volume_view is not None:
            if self.cur_volume_view.direction == 0:
                axes[:,(0,1)] *= -1
            else:
                axes *= -1.
        return axes

    def clearCaches(self):
        self.oldzs = None
        self.oldtri = None
        self.clearZsliceCache()

    def clearZsliceCache(self):
        self.prevZslice = -1
        self.prevZslicePts = None

    def aligned(self):
        if self.cur_volume_view is None:
            return False
        if self.cur_volume_view.direction != self.fragment.direction:
            return False
        return True

    # recursion_ok determines whether to call setLocalPoints in
    # "echo" fragments.  But this is safe to call only if all
    # fragment views have had their current volume view set.
    # NOTE that Fragment.setLocalPoints sets stpoints,
    # but TrglFragment.setLocalPoints does not.
    def setLocalPoints(self, recursion_ok, always_update_zsurf=True):
        # print("set local points", self.cur_volume_view.volume.name)
        # print("set local points", self.fragment.name)
        self.local_points_modified = Utils.timestamp()
        if self.cur_volume_view is None:
            self.fpoints = np.zeros((0,4), dtype=np.float32)
            self.vpoints = np.zeros((0,4), dtype=np.float32)
            return
        self.fpoints = self.cur_volume_view.volume.globalPositionsToTransposedIjks(self.fragment.gpoints, self.fragment.direction)
        npts = self.fpoints.shape[0]
        if npts > 0:
            indices = np.reshape(np.arange(npts), (npts,1))
            self.fpoints = np.concatenate((self.fpoints, indices), axis=1)

        self.vpoints = self.cur_volume_view.volume.globalPositionsToTransposedIjks(self.fragment.gpoints, self.cur_volume_view.direction)
        # self.stpoints = self.vpoints[:,0:2]
        # self.stpoints = self.fpoints[:,0:2]
        gai = self.cur_volume_view.volume.globalAxisFromTransposedAxis(0, self.fragment.direction)
        gaj = self.cur_volume_view.volume.globalAxisFromTransposedAxis(1, self.fragment.direction)
        self.stpoints = self.fragment.gpoints[:,(gai,gaj)]
        self.normals = np.zeros((npts, 3), dtype=np.float32)
        self.normals[:,2] = -1.
        # self.xyzmin = (0.,0.,0.)
        # self.xyzmin = (0.,0.,0.)
        self.working_vpoints = np.full((len(self.vpoints),),True)
        self.working_trgls = np.full((0,),True)
        npts = self.vpoints.shape[0]
        '''
        if npts > 0:
            indices = np.reshape(np.arange(npts), (npts,1))
            # print(self.vpoints.shape, indices.shape)
            self.vpoints = np.concatenate((self.vpoints, indices), axis=1)
            # print(self.vpoints[0])
        '''
        indices = np.reshape(np.arange(npts), (npts,1))
        self.vpoints = np.concatenate((self.vpoints, indices), axis=1)
        ''''''
        if not self.mesh_visible:
            self.zsurf = None
            self.ssurf = None
            self.tri = None
            return
        # print("set fpoints and vpoints")
        # print ("creating zsurf for", self.fragment.name)
        # if always_update_zsurf or self.live_zsurf_update:
        #     self.createZsurf()
        # print("created zsurf")
        # else:
        #     self.triangulate()
        # print("before czs")
        self.createZsurf(always_update_zsurf or self.live_zsurf_update)
        # print("after czs")
        self.calculateSqCm()
        ntrgl = 0
        if self.tri is not None:
            ntrgl = len(self.tri.simplices)
        self.working_trgls = np.full((ntrgl,),True)
        # print("calculated sq cm")
        if not recursion_ok:
            return
        for fv in self.project_view.fragments.values():
            echo = fv.fragment.params.get('echo', '')
            if echo == self.fragment.name:
                fv.echoPointsFrom(self)
                fv.setLocalPoints(True, always_update_zsurf)

    def setLiveZsurfUpdate(self, lzu):
        if lzu == self.live_zsurf_update:
            return
        self.live_zsurf_update = lzu
        if lzu:
            self.setLocalPoints(True)

    def echoPointsFrom(self, orig):
        # print("echo from",orig.fragment.name,"to",self.fragment.name)
        print("echo from %s (%d) to %s (%d)"%(
            orig.fragment.name, len(orig.fragment.gpoints),
            self.fragment.name, len(self.fragment.gpoints),))
        params = self.fragment.params
        self.fragment.gpoints = np.copy(orig.fragment.gpoints)
        infill = params.get("infill", 0)
        if self.cur_volume_view is None:
            self.cur_volume_view = orig.cur_volume_view
        if infill > 0 and self.cur_volume_view is not None:
            print("infill",infill)
            vol = self.cur_volume_view.volume
            print("vol", vol.name)
            newgijks = self.fragment.createInfillPoints(infill)
            self.fragment.gpoints = np.append(self.fragment.gpoints, newgijks, axis=0)
            self.setLocalPoints(True)

    # given node indices and a triangulation, return a list of the
    # neighboring node indices, plus the input node indices themselves
    def nodesNeighbors(self, tri, nodes):
        tris = tri.simplices
        # print("nodes", nodes)
        # print("tris", tris)
        # print("isin", np.isin(tris,nodes))
        trgl_idxs = (np.isin(tris, nodes)).any(1).nonzero()[0]
        trgls = tris[trgl_idxs]
        vrts = np.unique(trgls.flatten())
        return vrts

    # given a node index and a triangulation, return a list of the
    # neighboring node indices, plus the node itself
    def nodeNeighbors(self, tri, node_idx):
        tris = tri.simplices
        trgl_idxs = (tris==node_idx).any(1).nonzero()[0]
        trgls = tris[trgl_idxs]
        vrts = np.unique(trgls.flatten())
        # print("neighbors", vrts)
        return vrts

    def trglsVertices(self, tri, trgl_indices):
        tris = tri.simplices
        vrts = np.unique(tris[trgl_indices].flatten())
        return vrts

    def trglsNeighborsVertices(self, tri, trgl_indices):
        vrts = self.trglsVertices(tri, trgl_indices)
        return self.nodesNeighbors(tri, vrts)

    # given a set of node indices, return a bounding box
    # (minx, maxx, miny, maxy) containing all the nodes
    def nodesBoundingBox(self, tri, nodes):
        if tri is None:
            pts = self.fpoints[:,0:2]
        elif nodes is None:
            pts = tri.points
        else:
            pts = tri.points[nodes]
        # print(pts)
        if len(pts) == 0:
            return None
        minx, miny = np.min(pts, axis=0)
        maxx, maxy = np.max(pts, axis=0)
        # print("min",minx,miny,"max",maxx,maxy)
        # return(minx, miny, maxx, maxy)
        return ((minx,miny),(maxx,maxy))
    
    def computeFragRect(self):
        frag_rect = self.nodesBoundingBox(None, None)
        # print("fr", frag_rect)
        if frag_rect is not None:
           (minx, miny), (maxx, maxy) = frag_rect
           nk,nj,ni = self.cur_volume_view.trshape
           # if self.fragment.direction != self.cur_volume_view.direction:
           if not self.aligned():
               ni,nj,nk = nk,nj,ni
           minx = int(min(minx-1, ni))
           miny = int(min(miny-1, nj))
           minx = int(max(minx-1, 0))
           miny = int(max(miny-1, 0))
           maxx = int(max(maxx+1, 0))
           maxy = int(max(maxy+1, 0))
           maxx = int(min(maxx+1, ni))
           maxy = int(min(maxy+1, nj))
           frag_rect = (minx, miny, maxx, maxy)
           # print("fr2", frag_rect)
        return frag_rect

    def hideSkinnyTriangles(self):
        return FragmentView.hide_skinny_triangles

    def interpAndFilter(self, interp_method, tri):
        # print("wrapper", self.hideSkinnyTriangles())
        def interp(pts):
            zs = interp_method(pts)
            if self.hideSkinnyTriangles():
                simps = tri.find_simplex(pts)
                # zs[simps%2 == 0] = np.nan
                frag = self.fragment
                bads = frag.badBorderTrgls(tri, frag.badTrglsBySkinniness(tri, self.fragment.minRoundness()))
                # print("bads", len(bads), "/", len(tri.simplices))
                zs[np.isin(simps, bads)] = np.nan
            return zs
        return interp

    def workingZsurf(self):
        return self.zsurf

    def workingSsurf(self):
        return self.ssurf

    def workingVpoints(self):
        return self.working_vpoints

    # Whenever createZsurf is called, fpoints are re-triangulated,
    # so that fragment view triangles always look correct.
    # However, if do_update is False, z values (which are based
    # on the triangulation) are not recalculated.  The reason
    # for sometimes setting do_update to be False is that the
    # z calculation is relatively slow, so if there is a batch
    # of changes occuring in quick succession (the user is moving
    # a bunch of nodes, or the auto-segmentation is adding a
    # bunch of points), it is better to wait until after the
    # batch of changes before recalculating z values.
    def createZsurf(self, do_update=True):
        timer_active = False
        timer = Utils.Timer(timer_active)
        self.triangulate()
        timer.time("triangulate")
        if not do_update:
            return

        # If changed_rect is set to a rectangle rather than
        # None, it will be used as the bounds of the area
        # to be updated.
        changed_rect = None
        frag_rect = self.computeFragRect()
        oldtri = self.oldtri

        # If all these conditions are True, then it is possible
        # to update the zsurf within a smaller rectangle, rather than
        # over the entire surface.
        # https://stackoverflow.com/questions/66674537/python-numpy-get-difference-between-2-two-dimensional-array
        if oldtri is not None and self.tri is not None and self.oldzs is not None:
            # Find the bounding rectangle within which
            # to update the zsurf, based on the points and triangles
            # that have been changed since the last update

            # Need to check for changes in point positions in 3D, but
            # tri.points only has 2D point positions, so append the
            # z points
            oldpts = np.append(oldtri.points, self.oldzs[:,np.newaxis], axis=1)
            newpts = np.append(self.tri.points, self.fpoints[:,2:3], axis=1)
            # print("old new",oldpts.shape, newpts.shape)

            # Find points that have been deleted (oldpts minus newpts,
            # where "minus" is a set operation)
            # If a point has simply been moved, it will be detected
            # twice: as if the point at the old position had been deleted,
            # and the point at the new position had been added
            deleted_pts = Utils.setDiff2DIndex(oldpts, newpts)
            del_pts_rect = None
            if len(deleted_pts) > 0:
                # Neighboring points
                nidxs = self.nodesNeighbors(oldtri, deleted_pts)
                # Neighbors of neighboring points
                nnidxs = self.nodesNeighbors(oldtri, nidxs)
                del_pts_rect = self.nodesBoundingBox(oldtri, nnidxs)

            # Find points which have been added (newpts minus oldpts)
            added_pts = Utils.setDiff2DIndex(newpts, oldpts)
            add_pts_rect = None
            if len(added_pts) > 0:
                nidxs = self.nodesNeighbors(self.tri, added_pts)
                nnidxs = self.nodesNeighbors(self.tri, nidxs)
                add_pts_rect = self.nodesBoundingBox(self.tri, nnidxs)

            # rectUnion will correctly handle the case where either
            # (or both) of the input rects is None
            pts_rect = Utils.rectUnion(del_pts_rect, add_pts_rect)

            # For each simplex (triangle), sort its point
            # indices in ascending order, so that old and new
            # triangulations can more easily be compared.
            # As a result of the sorting, a large percentage
            # of the sorted triangles will be flipped compared
            # to their original orientation.
            oldtris = np.sort(oldtri.simplices)
            newtris = np.sort(self.tri.simplices)

            # For each triangle, replace each point index by the
            # point xy values.  The xy values, rather than the indices,
            # will be used to compare triangulations, because
            # the indices will change whenever a point is deleted.
            # Bear in mind that if the points simply move a little,
            # without affecting the original triangulation topology,
            # this will still be seen as a change in the triangulation,
            # because the xy locations will have changed even if the 
            # indices haven't.
            oldtrixys = oldtri.points[oldtris].reshape(-1,6)
            newtrixys = self.tri.points[newtris].reshape(-1,6)

            # old triangulation minus new triangulation
            deleted_tris = Utils.setDiff2DIndex(oldtrixys, newtrixys)
            del_tris_rect = None
            if len(deleted_tris) > 0:
                vrts = self.trglsNeighborsVertices(oldtri, deleted_tris)
                if len(vrts) > 0:
                    del_tris_rect = self.nodesBoundingBox(oldtri, vrts)

            # new triangulation minus old triangulation
            added_tris = Utils.setDiff2DIndex(newtrixys, oldtrixys)
            add_tris_rect = None
            if len(added_tris) > 0:
                vrts = self.trglsNeighborsVertices(self.tri, added_tris)
                if len(vrts) > 0:
                    add_tris_rect = self.nodesBoundingBox(self.tri, vrts)

            tris_rect = Utils.rectUnion(del_tris_rect, add_tris_rect)

            changed_rect = Utils.rectUnion(pts_rect, tris_rect)


            '''
            # Diagnostics (keep in case they are needed later)
            if Utils.rectIsValid(changed_rect):
                print("rects", self.fragment.name, len(deleted_pts), len(added_pts), len(deleted_tris), len(added_tris))
                if pts_rect is not None and pts_rect != changed_rect:
                    print("p  ", pts_rect)
                if tris_rect is not None and pts_rect != changed_rect:
                    print("t  ", tris_rect)
                print("c  ", changed_rect)
            '''

            if not Utils.rectIsValid(changed_rect):
                return

            if changed_rect is not None:
                (minx, miny), (maxx, maxy) = changed_rect
                if minx >= maxx or miny >= maxy:
                    # print("nulling changed_rect")
                    changed_rect = None
                else:
                    # nk,nj,ni = self.cur_volume_view.trshape
                    nk,nj,ni = self.cur_volume_view.trshape
                    # if self.fragment.direction != self.cur_volume_view.direction:
                    if not self.aligned():
                        ni,nj,nk = nk,nj,ni
                    minx = int(max(minx-1, 0))
                    miny = int(max(miny-1, 0))
                    maxx = int(min(maxx+1, ni))
                    maxy = int(min(maxy+1, nj))
                    changed_rect = (minx, miny), (maxx, maxy)

        '''
        if changed_rect is None and frag_rect is not None:
            print("frag rect", frag_rect)
            # frag_rect = None
        if changed_rect is not None:
            print("changed rect", changed_rect)
        '''

        self.oldzs = np.copy(self.fpoints[:,2])
        self.oldtri = self.tri
        timer.time("diff")
        nk,nj,ni = self.cur_volume_view.trshape
        # if self.fragment.direction != self.cur_volume_view.direction:
        if not self.aligned():
            ni,nj,nk = nk,nj,ni
        ns = (ni,nj,nk)
        if changed_rect is None or self.tri is None:
            self.zsurf = np.zeros((nj,ni), dtype=np.float32)
            self.zsurf.fill(np.nan)
            self.clearZsliceCache()
        self.osurf = None
        if self.tri is not None:
            inttype = ""
            inttype = self.fragment.params.get('interpolation', '')
            if inttype == "linear":
                inner_interp = LinearNDInterpolator(self.tri, self.fpoints[:,2])
            elif inttype == "nearest":
                inner_interp = NearestNDInterpolator(self.tri, self.fpoints[:,2])
            else:
                inner_interp = CloughTocher2DInterpolator(self.tri, self.fpoints[:,2])
            # for testing:
            interp = self.interpAndFilter(inner_interp, self.tri)
            if changed_rect is None:
                if frag_rect is None:
                    print("frag_rect unexpectedly None")
                    pts = np.indices((ni, nj)).transpose()
                    # print("pts shape", pts.shape)
                    self.zsurf = interp(pts)
                    self.clearZsliceCache()
                else:
                    minx, miny, maxx, maxy = frag_rect
                    # print("fr",minx,miny,maxx,maxy)
                    nx = maxx-minx
                    ny = maxy-miny
                    if nx < 0 or ny < 0:
                        print("out of order", minx, miny, maxx, maxy)
                    # print("later", minx, miny, maxx, maxy)
                    pts = np.indices((nx, ny))
                    pts[0,:,:] += int(minx)
                    pts[1,:,:] += int(miny)
                    pts = pts.transpose()
                    local_zsurf = interp(pts)
                    # print("shapes", self.zsurf.shape, local_zsurf.shape)
                    self.zsurf[miny:maxy,minx:maxx] = local_zsurf
                    self.clearZsliceCache()
            else:
                (minx, miny), (maxx, maxy) = changed_rect
                # print("cr",minx,miny,maxx,maxy)
                nx = maxx-minx
                ny = maxy-miny
                pts = np.indices((nx, ny))
                pts[0,:,:] += int(minx)
                pts[1,:,:] += int(miny)
                pts = pts.transpose()
                local_zsurf = interp(pts)
                # print("shapes", self.zsurf.shape, local_zsurf.shape)
                self.zsurf[miny:maxy,minx:maxx] = local_zsurf
                self.clearZsliceCache()
            timer.time("zsurf")
            overlay = self.fragment.params.get('overlay', '')
            if overlay == "diff":
                # ct = CloughTocher2DInterpolator(self.tri, self.fpoints[:,2])
                lin = LinearNDInterpolator(self.tri, self.fpoints[:,2])
                pts = np.indices((ni, nj)).transpose()
                self.osurf = self.zsurf - lin(pts)
                amin = np.nanmin(self.osurf)
                amax = np.nanmax(self.osurf)
                print(amin, amax)
                # self.osurf[amax-self.osurf<5] *= 2.
                # self.osurf[self.osurf-amin<5] *= 2.

            elif overlay == "zsurf":
                zmin = np.nanmin(self.zsurf)
                zmax = np.nanmax(self.zsurf)
                self.osurf = -(self.zsurf - .5*(zmin+zmax))
            elif overlay == "triangle":
                simps = self.tri.simplices
                verts = self.tri.points
                v0 = verts[simps[:,0]]
                v1 = verts[simps[:,1]]
                v2 = verts[simps[:,2]]
                v01 = v1-v0
                v02 = v2-v0
                v12 = v2-v1
                l01 = np.sqrt((v01*v01).sum(1))
                l02 = np.sqrt((v02*v02).sum(1))
                l12 = np.sqrt((v12*v12).sum(1))
                d12 = (v01*v02).sum(1)/(l01*l02)
                d01 = (v02*v12).sum(1)/(l02*l12)
                d02 = -(v01*v12).sum(1)/(l01*l12)
                ds = np.array((d01,d02,d12)).transpose()
                # print("ds shape", ds.shape)
                dmax = np.amax(ds, axis=1)
                # print("dmax shape", dmax.shape)
                dmax = np.insert(dmax, 0, 0.)
                # print("dmax shape", dmax.shape)
                simpar = self.tri.find_simplex(pts)
                # print("simpar shape", simpar.shape)
                maxes = dmax[simpar+1]
                # print("maxes shape", maxes.shape)

                maxes[maxes == -1] = np.nan
                self.osurf = maxes*maxes*maxes*maxes
                self.osurf -= .5
                timer.time("simplex")
                # TODO for testing only
                # self.osurf = None
            if self.osurf is not None:
                mn = np.nanmin(self.osurf)
                mx = np.nanmax(self.osurf)
                amax = max(abs(mn),abs(mx))
                if amax > 0:
                    self.osurf /= amax
                self.gt0 = self.osurf > 0
                self.lt0 = self.osurf < 0
                self.ogt0 = (65536*self.osurf[self.gt0]).astype(np.uint16)
                self.olt0 = (-65536*self.osurf[self.lt0]).astype(np.uint16)


        if self.line is not None and self.lineAxis > -1:
            # print("createZsurf from line")
            spline = CubicSpline(
                    self.line[:,0], self.line[:,1], extrapolate=False)
            xs = np.arange(ns[1-self.lineAxis])
            ys = spline(xs)
            # print(self.zsurf.shape)
            # print(xs.shape)
            # print(self.lineAxis, self.lineAxisPosition)
            # print("line", self.fragment.name, self.fragment.direction, self.cur_volume_view.direction, self.lineAxis, self.lineAxisPosition, self.zsurf.shape)
            zshape = self.zsurf.shape
            lap = self.lineAxisPosition
            if self.lineAxis == 0 and lap >=0 and lap < zshape[1]:
                self.zsurf[:,lap] = ys
                self.clearZsliceCache()
            elif self.lineAxis == 1 and lap >= 0 and lap < zshape[0]:
                self.zsurf[lap,:] = ys
                self.clearZsliceCache()
            # print(ys)

        # TODO: This shouldn't be a problem!
        # if self.fragment.direction != self.cur_volume_view.direction:
        #     self.ssurf = None
        #     return

        # can happen when initializing an "echo" fragment
        # while switching to a different volume
        # if self.cur_volume_view.volume.trdatas is None:
        #     return
        
        if changed_rect is None:
            if frag_rect is None:
                # happens if fragment has no nodes
                # print("frag_rect is still unexpectedly None")
                # ssi = np.indices((ni, nj))
                self.ssurf = np.zeros((nj,ni), dtype=np.uint16)
                return
            else:
                minx, miny, maxx, maxy = frag_rect
                # print("fr2", frag_rect)
                nx = maxx-minx
                ny = maxy-miny
                ssi = np.indices((nx, ny))
                ssi[0,:,:] += int(minx)
                ssi[1,:,:] += int(miny)
        else:
            (minx, miny), (maxx, maxy) = changed_rect
            # print("cr2", changed_rect)
            nx = maxx-minx
            ny = maxy-miny
            ssi = np.indices((nx, ny))
            ssi[0,:,:] += int(minx)
            ssi[1,:,:] += int(miny)
        # print("ssi shape",ssi.shape, ssi.dtype)
        xs = ssi[0].flatten()
        ys = ssi[1].flatten()
        # print ("xs shape", xs.shape, xs.dtype)
        xys = np.array((ys,xs), dtype = xs.dtype)
        # print ("xys shape", xys.shape, xys.dtype)
        zs = self.zsurf[tuple(xys)]
        # print ("zs shape", zs.shape, zs.dtype)
        xyzs = np.array((zs,ys,xs))
        # print ("xyzs shape", xyzs.shape, xyzs.dtype)
        xyzsn = xyzs[:,~np.isnan(zs)]
        # print ("xyzsn shape", xyzsn.shape, xyzsn.dtype)

        # Occurs when fragment has only 1 point
        # or triangulated surface is very small
        if xyzsn.shape[1] == 0:
            # print("xyzsn wrong size")
            self.ssurf = None
            return
        ixyzs = np.rint(xyzsn).astype(np.int32)
        # print ("ixyzs shape", ixyzs.shape, ixyzs.dtype)
        # print("cvv", self.cur_volume_view, self.cur_volume_view.volume, self.cur_volume_view.volume.trdatas, self.fragment, self.fragment.direction)
        ftrdata = self.cur_volume_view.volume.trdatas[self.fragment.direction]
        ## print("ixyzs max", ixyzs.max(axis=1))
        ## print("trdata", trdata.shape)
        # print("ixyzs rot max", ixyzs[(2,0,1),:].max(axis=1))
        # print("rixyzs max", rixyzs.max(axis=1))

        # self.ssurf might be None if previous triangulation
        # was too thin
        if changed_rect is None or self.ssurf is None:
            self.ssurf = np.zeros((nj,ni), dtype=np.uint16)
        else:
            self.ssurf[miny:maxy,minx:maxx] = np.zeros((maxy-miny,maxx-minx), dtype=np.uint16)
        # print ("ssurf shape", self.ssurf.shape, self.ssurf.dtype)
        # print ("trdata shape", self.cur_volume_view.trdata.shape, self.cur_volume_view.trdata.dtype)
        ## print("ssurf",self.ssurf.shape)

        # recall that index order is k,j,i
        ixyzs = ixyzs[:,ixyzs[0,:]<ftrdata.shape[0]]
        ixyzs = ixyzs[:,ixyzs[0,:]>=0]
        # use_linear_interpolation = True
        # TODO: commented out this code because it should
        # no longer be needed, since createZsurf should
        # only be called when exporting the fragment as
        # an obj file.
        # The code below no longer works because trdata is
        # now 4D, not 3D
        ''' 
        vol = self.cur_volume_view.volume
        vol.setImmediateDataMode(True)
        if FragmentView.use_linear_interpolation:
            # print("linear")
            z0s = ixyzs[0,:]
            ss0 = ftrdata[(z0s, ixyzs[1,:], ixyzs[2,:])]
            z1s = np.minimum(ixyzs[0,:]+1, ftrdata.shape[0]-1)
            ss1 = ftrdata[(z1s, ixyzs[1,:], ixyzs[2,:])]
            xyzsn = xyzsn[:,np.rint(xyzsn[0,:])<ftrdata.shape[0]]
            xyzsn = xyzsn[:,np.rint(xyzsn[0,:])>=0]
            zfs = xyzsn[0]-z0s
            ssi = ss0*(1.-zfs)+ss1*(zfs)
            self.ssurf[(ixyzs[1,:],ixyzs[2,:])] = np.minimum(ssi, 65535)
        else: # nearest neighbor
            # print("nn")
            self.ssurf[(ixyzs[1,:],ixyzs[2,:])] = ftrdata[(ixyzs[0,:], ixyzs[1,:], ixyzs[2,:])]
        vol.setImmediateDataMode(False)
        '''


        timer.time("ssurf")


    # returns zsurf points, as array of [ipos, jpos] values
    # for the slice with the given axis and axis position
    # (axis and position relative to volume-view axes)
    def getZsurfPoints(self, vaxis, vaxisPosition):
        if self.zsurf is None:
            return
        faxis = vaxis
        vnk, vnj, vni = self.cur_volume_view.trshape
        fnk, fnj, fni = vnk, vnj, vni
        if not self.aligned():
            faxis = 2-vaxis
            fni, fnj, fnj = vnk, vnj, vni
        # print()
        # print(vaxis, vaxisPosition)
        if faxis == 0 or faxis == 1:
            vlen = self.zsurf.shape[1-faxis]
            # Ideally, would just do:
            #   if faxis == 0:
            #      jvec = self.zsurf[:,vaxisPosition]
            #   else:
            #      jvec = self.zsurf[vaxisPosition,:]
            # The problem is that at the edges of the fragment,
            # zsurf may not extend all the way to the
            # edge (not sure why, maybe something to do with
            # moving the nodes slightly during triangulation?).
            # So if jvec only contains nans (meaning that it
            # is off the edge), shift vaxisPosition by 1 and -1
            # to try to pick up the edge of the zsurf.
            for delta in [0,-1,1]:
                v = vaxisPosition+delta
                if v >= vlen:
                    continue
                if v < 0:
                    continue
                if faxis == 0:
                    jvec = self.zsurf[:,v]
                else:
                    jvec = self.zsurf[v,:]
                # print(" ",delta, (~np.isnan(jvec)).sum())

                # break if any non-nan points are found
                if not np.isnan(jvec).all():
                    break
            ivec = np.arange(len(jvec))
            pts = np.array((ivec,jvec)).transpose()
            pts = pts[~np.isnan(pts[:,1])]
            if not self.aligned():
                pts = pts[:,(1,0)]
            return pts
        else: # faxis == 2
            # The so-called z slice is a relatively expensive
            # operation, and should not be performed unless "z"
            # or the zsurf has changed.  So cache the results.
            if self.prevZslicePts is not None and self.prevZslice == vaxisPosition:
                return self.prevZslicePts
            frag_rect = self.computeFragRect()
            if frag_rect is not None:
                minx, miny, maxx, maxy = frag_rect
                # print(self.fragment.name,minx,miny,maxx,maxy)
                nx = maxx-minx
                ny = maxy-miny
                # pts = np.indices((nx, ny))
                pts = np.indices((ny, nx))
                pts[0,:,:] += int(miny)
                pts[1,:,:] += int(minx)
                # print("shape pts",pts.shape)
                # print(pts.shape, nx, ny)
                pts = pts[:, np.rint(self.zsurf[miny:maxy,minx:maxx])==vaxisPosition].transpose()
                if self.aligned():
                    pts = pts[:,(1,0)]
                # print("len pts",len(pts), pts.shape)
            else:
                pts = None
            self.prevZslice = vaxisPosition
            self.prevZslicePts = pts
            return pts

    def triangulate(self):
        self.tri = None
        self.line = None
        self.lineAxis = -1
        if self.fpoints.shape[0] <= 1:
            return

        # check if points all lie on the same line, parallel
        # to one of the axes
        iuniques = len(np.unique(self.fpoints[:,0]))
        juniques = len(np.unique(self.fpoints[:,1]))
        if iuniques == 1 and juniques > 1:
            # points share a common i value
            self.lineAxis = 0
        elif juniques == 1 and iuniques > 1:
            # points share a common j value
            self.lineAxis = 1
        if self.lineAxis >= 0:
            self.lineAxisPosition = int(self.fpoints[0,self.lineAxis])
            self.line = self.fpoints[:, (1-self.lineAxis, 2, 3)]
            # print("sl1",self.line)
            self.line = self.line[self.line[:,0].argsort()]
            # print(self.lineAxis, self.lineAxisPosition)
            # print(self.fpoints)
            # print("sl1",self.line)
            return

        try:
            nppoints = self.fpoints[:,0:2]
            # Mathematicians hate this trick!
            # For certain positions of points (for instance,
            # if four or more points lie on the
            # circumference of a circle), Delaunay
            # triangulation has a non-unique solution.
            # When successive calls to Delaunay() return
            # different (yet still valid) triangulations of the
            # same points, this can force an unnecessary and
            # time-consuming recomputation of zsurf.  To make
            # non-unique solutions less likely, shift each point
            # by a tiny but determinate (non-random) amount, based on
            # the point's location (can't use the index, because indices
            # change whenever a point is deleted).
            # Side effect: self.tri.points is based on shifted_nppoints
            # rather than on nppoints (fpoints), which may cause unexpected
            # behavior in code that is unaware of this shift.
            shifted_nppoints = nppoints.copy().astype(dtype=np.float64)
            # ind = np.arange(shifted_nppoints.shape[0], dtype=np.int32)
            ind = (nppoints[:,0]*1019+nppoints[:,1]*1013).astype(np.int64)
            eps = 1./(1024*1024)
            # 503, 509, 1013 and 1019 are prime
            shifted_nppoints[:,0] += eps*np.remainder(ind, 503)
            shifted_nppoints[:,1] += eps*np.remainder(ind, 509)

            self.tri = Delaunay(shifted_nppoints)
            # Can't do this!  self.tri.points cannot be reset
            # self.tri.points = nppoints
        except QhullError as err:
            print("qhull error", str(err))
            self.tri = None

    def getPointsOnSlice(self, axis, i):
        # matches = self.vpoints[(self.vpoints[:, axis] == i)]
        # print(self.vpoints.shape)
        matches = self.vpoints[(self.vpoints[:, axis] >= i-.5) & (self.vpoints[:, axis] < i+.5)]
        return matches

    def vijkToFijk(self, vijk):
        if self.aligned():
            fijk = vijk
        else:
            fijk = (vijk[2], vijk[1], vijk[0])
        return fijk

    def fijkToVijk(self, fijk):
        if self.aligned():
            vijk = fijk
        else:
            vijk = (fijk[2], fijk[1], fijk[0])
        return vijk

    # stxy is ignored
    def addPoint(self, tijk, stxy):
        # ijk using volume-view's direction
        if tijk is None: # picked point is outside of current fragment
            return
        fijk = self.vijkToFijk(tijk)

        # use fijk rounded to nearest integer (note that this
        # may have consequences if current volume is coarser
        # than global volume
        ijk = np.rint(np.array(fijk))
        # if same ij (in fragment's direction) as existing
        # point, replace point with existing point
        ij = ijk[0:2]
        matches = np.where((np.rint(self.fpoints[:, 0:2]) == ij).all(axis=1))[0]
        # print(matches)
        # Check if there is already a point at this 2D location
        if matches.shape[0] > 0:
            # print("duplicate at", tijk)
            # print("deleting duplicates at row", matches)
            # print("    ", self.vpoints[matches[0]])
            # delete old point if exists at same ij as new point
            # self.fragment.gpoints = np.delete(self.fragment.gpoints, matches, 0)
            # Move existing point rather than deleting and replacing
            # it, to avoid reindexing the list of points
            print("addPoint: duplicate at", ij, tijk)
            self.movePoint(matches[0], tijk, True, False)
            return
        # create new point
        gijk = self.cur_volume_view.transposedIjkToGlobalPosition(tijk)
        self.pushFragmentState()
        self.fragment.gpoints = np.append(self.fragment.gpoints, np.reshape(gijk, (1,3)), axis=0)
        # print(self.lpoints)
        self.setLocalPoints(True, False)
        self.fragment.notifyModified()

    def deletePointByIndex(self, index):
        if index >= 0 and index < len(self.fragment.gpoints):
            self.pushFragmentState()
            self.fragment.gpoints = np.delete(self.fragment.gpoints, index, 0)
        self.fragment.notifyModified()
        self.setLocalPoints(True, False)

    def workingTrgls(self):
        return self.working_trgls

    def hasWorkingNonWorking(self):
        return (True, False)

    def workingLine(self):
        return self.line

    def workingLineAxis(self):
        return self.lineAxis

    def workingLineAxisPosition(self):
        return self.lineAxisPosition

    def trgls(self):
        if self.tri is None:
            # Return empty array instead of None for new fragments
            return np.zeros((0,3), dtype=np.int32)
        return self.tri.simplices

    # return True if succeeds, False if fails
    # Note that update_xyz and update_st are ignored here;
    # st is always updated due to the call to FragmentView.setLocalPoints() 
    def movePoint(self, index, new_vijk, update_xyz, update_st):
        # print("mp a")
        old_fijk = self.fpoints[index]
        new_fijk = self.vijkToFijk(new_vijk)
        new_matches = np.where((np.rint(self.fpoints[:, 0:2]) == np.rint(new_fijk[0:2])).all(axis=1))[0]
        if (round(old_fijk[0]) != round(new_fijk[0]) or round(old_fijk[1]) != round(new_fijk[1])) and new_matches.shape[0] > 0:
            print("movePoint point already exists at this ij", new_vijk)
            return False
        # print("mp b")
        new_gijk = self.cur_volume_view.transposedIjkToGlobalPosition(new_vijk)
        # print("mp b2")
        # print(self.fragment.gpoints)
        # print(match, new_gijk)
        self.pushFragmentState()
        # print("mp c")
        self.fragment.gpoints[index, :] = new_gijk
        # print(self.fragment.gpoints)
        self.fragment.notifyModified()
        # NOTE that this will set stpoints as well as fpoints and vpoints
        self.setLocalPoints(True, False)
        # print("mp d")
        return True

    def pushFragmentState(self):
        """Push the current list of gpoints onto the stack in preparation for changing gpoints."""
        gpoints_copy = np.copy(self.fragment.gpoints)
        self.fragment.gpoints_history.append(gpoints_copy)

    def popFragmentState(self):
        """Replace current gpoints with top of the stack, and update."""
        hist_size =  len(self.fragment.gpoints_history)
        if hist_size > 0:
            self.fragment.gpoints = self.fragment.gpoints_history.pop()
            self.fragment.notifyModified()
            self.setLocalPoints(True, False)

    def pushFragmentStateOld(self):
        """Push the current list of gpoints onto the stack in preparation for changing gpoints."""
        # print("pfs a")
        gpoints_copy = np.copy(self.fragment.gpoints)
        # print("pfs b")
        try:
            self.fragment.gpoints_history.put(gpoints_copy, block=False)
        except:
            # print("pfs e")
            self.fragment.gpoints_history.get()
            self.fragment.gpoints_history.put(gpoints_copy, block=False)
        # print("pfs c")

    def popFragmentStateOld(self):
        """Replace current gpoints with top of the stack, and update."""
        hist_size=  self.fragment.gpoints_history.qsize()
        if hist_size > 0:
            try:
                self.fragment.gpoints = self.fragment.gpoints_history.get(block=False)
            except:
                return
            self.fragment.notifyModified()
            self.setLocalPoints(True, False)


