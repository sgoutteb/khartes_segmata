def autoExtrapolate(self, sign, ij):
        volume = self.volume_view
        if volume is None :
            return
        if self.currentFragmentView() is None:
            return
        if not self.currentFragmentView().allowAutoExtrapolation():
            return False
        ww = self.size().width()
        wh = self.size().height()
        # ij* are corners of the viewing window, in data coordinates
        ij0 = self.xyToIj((0,0))
        ij1 = self.xyToIj((ww,wh))
        ijo0 = ij0
        ijo1 = ij1
        margin = 32
        # add a margin of 32 pixels (in data coordinates)
        ij0m = (ij0[0]-margin,ij0[1]-margin)
        ij1m = (ij1[0]+margin,ij1[1]+margin)

        zarr_max_width = self.getZarrMaxWidth()
        rs = volume.getSliceBounds(self.axis, volume.ijktf, zarr_max_width)
        if rs is None:
            return
        (sx1,sy1),(sx2,sy2) = rs
        slc = volume.getSliceInRange(
                volume.trdata, slice(sx1,sx2), slice(sy1,sy2), 
                volume.ijktf[self.axis], self.axis)
        # print(volume.trdata.shape, rs, slc.shape, (ij0m,ij1m))
        sw = slc.shape[1]
        sh = slc.shape[0]
        s0 = (sx1,sy1)
        s1 = (sx2,sy2)

        # print("s0,s1",s0,s1)
        ri = Utils.rectIntersection((ij0m,ij1m), (s0,s1))
        if ri is None:
            return
        # print("ri",ri)
        ij0 = ri[0]
        ij1 = ri[1]
        ri = Utils.rectIntersection((ij0,ij1), ((ij[0]-500,ij[1]-500),(ij[0]+500,ij[1]+500)))
        if ri is None:
            return
        # print("ri",ri)
        ij0 = ri[0]
        ij1 = ri[1]
        # print("autosegment", ij, sign, ij0, ij1)
        if ij[0] < ij0[0] or ij[0] >= ij1[0]:
            return
        if ij[1] < ij0[1] or ij[1] >= ij1[1]:
            return
        st = ST((slc[int(ij0[1]-s0[1]):int(ij1[1]-s0[1]),int(ij0[0]-s0[0]):int(ij1[0]-s0[0])]).astype(np.float64)/65535.)
        # print ("st created", st.image.shape)
        st.computeEigens()
        # print ("eigens computed")
        dij = (ij[0]-ij0[0], ij[1]-ij0[1])
        # min distance between computed auto-pick points
        # note this is in units of data-volume voxel size,
        # which differ from that of the original data,
        # due to subsampling
        min_delta = 5
        ijk = self.ijToTijk(ij0)
        gxyz = self.volume_view.transposedIjkToGlobalPosition(ijk)
        gaxis = self.volume_view.globalAxisFromTransposedAxis(self.iIndex)
        gstep = self.volume_view.volume.gijk_steps[gaxis]
        # attempt to align the computed points so that they
        # lie at global coordinates (along the appropriate axis)
        # that are mutiples of min_delta.  Seems to work
        # correctly in sub-sampled data volumes as well.
        min_delta_shift = (gxyz[gaxis]/gstep) % min_delta
        y = st.call_ivp(dij, sign, 5.)
        if y is None:
            print("no y values")
            return
        # print("pts", y.shape)
        pts = st.sparse_result(y, min_delta_shift, min_delta)
        if pts is None:
            print("no points")
            return
        # print("sparse pts", pts.shape)
        print (len(pts),"points returned")
        pts[:,0] += ij0[0]
        pts[:,1] += ij0[1]
        # print("xs",pts[:,0])
        zsurf_update = self.window.live_zsurf_update
        self.window.setLiveZsurfUpdate(False)
        for pt in pts:
            # print("   ", pt)
            if pt[0] < ijo0[0] or pt[0] >= ijo1[0] or pt[1] < ijo0[1] or pt[1] >= ijo1[1]:
                break
            tijk = self.ijToTijk(pt)
            # print("adding point at",tijk)
            self.window.addPointToCurrentFragment(tijk)
        self.window.setLiveZsurfUpdate(zsurf_update)
        mpt = self.mapFromGlobal(QCursor.pos())
        mxy = (mpt.x(), mpt.y())
        self.setNearbyTiffAndNode(mxy)
        self.window.drawSlices()
