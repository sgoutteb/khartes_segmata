from fragment import Fragment, FragmentView
import numpy as np

class UmbilicusFragment(Fragment):
    def __init__(self, name, direction):
        super(UmbilicusFragment, self).__init__(name, direction)
        self.is_umbilicus = True # Flag to identify umbilicus fragments
        
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
        
    def createZsurf(self, do_update=True):
        # Override to skip triangulation and just sort points by Z
        if len(self.fpoints) <= 1:
            self.zsurf = None
            self.ssurf = None
            return
            
        # Sort points by Z coordinate
        sorted_points = self.fpoints[self.fpoints[:,2].argsort()]
        self.line = sorted_points
        
        # Create line segments between consecutive points
        self.segments = np.array([sorted_points[:-1], sorted_points[1:]]).transpose(1,0,2)
        
        # Skip the rest of createZsurf since we don't need triangulation
        self.zsurf = None 
        self.ssurf = None
        
    def triangulate(self):
        # Override to skip triangulation
        self.tri = None
        if self.fpoints.shape[0] <= 1:
            self.line = None
            return
            
        # Sort points by Z and store as line
        sorted_points = self.fpoints[self.fpoints[:,2].argsort()]
        self.line = sorted_points