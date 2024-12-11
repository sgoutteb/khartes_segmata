from fragment import Fragment, FragmentView
import numpy as np

class UmbilicusFragment(Fragment):
    def __init__(self, name, direction):
        super(UmbilicusFragment, self).__init__(name, direction)
        self.is_umbilicus = True # Flag to identify umbilicus fragments
        self.type = Fragment.Type.UMBILICUS
        
    def createView(self, project_view):
        return UmbilicusFragmentView(project_view, self)
        
    def meshExportNeedsInfill(self):
        return False # Umbilicus doesn't need infill since it's just a line
        
    def badTrglsBySkinniness(self, tri, min_roundness):
        # Override to do nothing since we don't use triangulation
        return []
        
    def badTrglsByMaxAngle(self, tri):
        # Override to do nothing since we don't use triangulation 
        return []
        
    def badTrglsByNormal(self, tri, pts):
        # Override to do nothing since we don't use triangulation
        return []

class UmbilicusFragmentView(FragmentView):
    def __init__(self, project_view, fragment):
        super(UmbilicusFragmentView, self).__init__(project_view, fragment)
        self.segments = None
        self.manual_points = None  # Store original user-placed points
        self.interpolated_points = None  # Store interpolated points
        
    def interpolatePoints(self):
        """Create linearly interpolated points between manual points"""
        if len(self.manual_points) < 2:
            self.interpolated_points = np.array([])
            return
            
        # Sort manual points by Z
        z_order = np.argsort(self.manual_points[:, 2])
        sorted_points = self.manual_points[z_order]
        
        # Update manual_points to maintain sorted order
        self.manual_points = sorted_points
        
        all_interpolated = []
        
        # Interpolate between each consecutive pair of points
        for i in range(len(sorted_points) - 1):
            p1 = sorted_points[i]
            p2 = sorted_points[i + 1]
            
            # Calculate number of points based on z distance
            z_dist = abs(p2[2] - p1[2])
            num_points = max(2, int(z_dist))  # At least 2 points to include endpoints
            
            # Create evenly spaced points between p1 and p2
            t = np.linspace(0, 1, num_points)[1:-1]  # Exclude endpoints to avoid duplicates
            
            # Linear interpolation for each dimension
            interp_points = np.array([
                p1[0] + (p2[0] - p1[0]) * t,  # x coordinates
                p1[1] + (p2[1] - p1[1]) * t,  # y coordinates
                p1[2] + (p2[2] - p1[2]) * t   # z coordinates
            ]).T
            
            all_interpolated.append(interp_points)
        
        # Combine all interpolated points
        if all_interpolated:
            self.interpolated_points = np.vstack(all_interpolated)
        else:
            self.interpolated_points = np.array([])

    def createZsurf(self, do_update=True):
        # Override to skip triangulation and just sort points by Z
        if len(self.fpoints) <= 1:
            self.zsurf = None
            self.ssurf = None
            self.line = None
            self.segments = None
            return
            
        # Sort points by Z coordinate and break ties using point indices
        # This ensures stable sorting when points have the same Z value
        indices = np.arange(len(self.fpoints))
        sorted_indices = np.lexsort((indices, self.fpoints[:,2]))
        sorted_points = self.fpoints[sorted_indices]
        self.line = sorted_points
        
        # Create line segments between consecutive points
        if len(sorted_points) > 1:
            self.segments = np.array([sorted_points[:-1], sorted_points[1:]]).transpose(1,0,2)
        else:
            self.segments = None
        
        # Skip the rest of createZsurf since we don't need triangulation
        self.zsurf = None 
        self.ssurf = None
        
    def triangulate(self):
        # Override to skip triangulation
        self.tri = None
        if self.fpoints.shape[0] <= 1:
            self.line = None
            self.segments = None
            return
            
        # Sort points by Z and break ties using point indices
        indices = np.arange(len(self.fpoints))
        sorted_indices = np.lexsort((indices, self.fpoints[:,2]))
        sorted_points = self.fpoints[sorted_indices]
        self.line = sorted_points
        return

    def getLinesOnSlice(self, axis, position):
        """Override to return line segments that intersect with the given slice"""
        if self.segments is None or len(self.segments) == 0:
            return None, None
        
        return None, None
            
        # Find segments that cross the slice plane
        crossings = []
        trglist = []
        
        for i, segment in enumerate(self.segments):
            p1, p2 = segment
            
            # Check if segment crosses the slice plane
            if (p1[axis] <= position <= p2[axis]) or (p2[axis] <= position <= p1[axis]):
                # Linear interpolation to find crossing point
                if abs(p2[axis] - p1[axis]) > 1e-10:  # Small threshold for floating point comparison
                    t = (position - p1[axis]) / (p2[axis] - p1[axis])
                    crossing = p1 + t * (p2 - p1)
                    crossings.append([crossing, crossing])  # Duplicate point to create a line segment
                    trglist.append(i)
                else:
                    # Points are at same height, use p1
                    crossings.append([p1, p1])
                    trglist.append(i)
                    
        if len(crossings) == 0:
            return None, None
            
        return np.array(crossings), np.array(trglist)

    def workingTrgls(self):
        """Override to return a boolean array for line segments"""
        if self.segments is None:
            return np.array([], dtype=bool)
        return np.ones(len(self.segments), dtype=bool)

    def trgls(self):
        """Override to return indices for line segments"""
        if self.segments is None:
            return np.array([], dtype=np.int32)
        return np.arange(len(self.segments), dtype=np.int32)

    def hasWorkingNonWorking(self):
        """Override to indicate all segments are working"""
        return (True, False)

    def addPoint(self, tijk, stxy):
        """Override addPoint to handle both manual and interpolated points"""
        # Convert to fragment's coordinate system
        fijk = self.vijkToFijk(tijk)
        
        # Round to nearest integer
        ijk = np.rint(np.array(fijk))
        
        # Find any existing points with the same Z coordinate
        z_matches = np.where(np.abs(self.fpoints[:, 2] - ijk[2]) < 1e-10)[0]
        
        if len(z_matches) > 0:
            # Delete existing point at this Z value
            self.pushFragmentState()
            self.fragment.gpoints = np.delete(self.fragment.gpoints, z_matches, 0)
            if self.manual_points is not None:
                # Also remove from manual points if it exists there
                manual_z_matches = np.where(np.abs(self.manual_points[:, 2] - ijk[2]) < 1e-10)[0]
                if len(manual_z_matches) > 0:
                    self.manual_points = np.delete(self.manual_points, manual_z_matches, 0)
    
        # Create new point
        gijk = self.cur_volume_view.transposedIjkToGlobalPosition(tijk)
        self.pushFragmentState()
        self.fragment.gpoints = np.append(self.fragment.gpoints, np.reshape(gijk, (1,3)), axis=0)
        
        # Add to manual points array
        if self.manual_points is None:
            self.manual_points = np.reshape(gijk, (1,3))
        else:
            self.manual_points = np.append(self.manual_points, np.reshape(gijk, (1,3)), axis=0)
        
        # If we have more than 2 manual points, create interpolated points
        if len(self.manual_points) >= 2:
            self.interpolatePoints()
            if self.interpolated_points is not None and len(self.interpolated_points) > 0:
                # Update fragment points to include both manual and interpolated points
                self.fragment.gpoints = np.vstack((self.manual_points, self.interpolated_points))
        
        self.setLocalPoints(True, False)
        self.fragment.notifyModified()