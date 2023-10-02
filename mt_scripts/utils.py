
"""
Common functionality
"""

__author__ = 'Antonio Martinez-Sanchez'

import os
import shutil
import vtk
import csv
import math
import numpy as np
import affine

from vtkmodules.util import numpy_support

# CONSTANTS

PI_2 = 2 * np.pi
VTK_RAY_TOLERANCE = 0.000001 # 0.001

# FUNCTIONS


def gen_uni_s2_sample(center, rad):
    """
    Generates a coordinate from uniformly random distribution on a sphere
    :param center: sphere center
    :param rad: sphere radius
    :return: the random coordinate generated
    """
    X = np.random.randn(1, 3)[0]
    norm = rad / np.linalg.norm(X)
    X *= norm
    return X + center


def points_distance(a, b):
    """
    Computes the Euclidean distance between two point
    :param a: input point a
    :param b: input point b
    :return: the Euclidean distance between a an b: d(a,b)
    """
    hold = b - a
    return math.sqrt((hold * hold).sum())


def poly_max_distance(vtp):
    """
    Computes the maximum distance in vtkPolyData
    :param vtp: input vtkPolyData
    :return: the maximum distance as real value
    """
    if vtp.GetNumberOfPoints() <= 0:
        return 0
    else:
        mx = 0
        ref_p = np.asarray(vtp.GetPoint(0))
        for i in range(1, vtp.GetNumberOfPoints()):
            hold_p = np.asarray(vtp.GetPoint(i))
            hold_mx = points_distance(ref_p, hold_p)
            if hold_mx > mx:
                mx = hold_mx
        return mx


def iso_surface(tomo, th, flp=None, closed=False, normals=None):
    """
    Iso-surface on an input 3D volume
    :param tomo: input 3D numpy array
    :param th: iso-surface threshold
    :param flp: if not None (default) it specifies the axis to flip (valid: 0, 1 or 3)
    :param closed: if True (default False) if forces to generate a closed surface, VERY IMPORTANT: closed output
    is only guaranteed for input boolean tomograms
    :param normals: normals orientation, valid None (default), 'inwards' and 'outwards'. Any value different from None
                    reduces surface precision
    :return: a vtkPolyData object only made up of triangles
    """

    # Marching cubes configuration
    march = vtk.vtkMarchingCubes()
    tomo_vtk = numpy_to_vti(tomo)
    if closed:
        # print str(tomo_vtk.GetExtent()), str(tomo.shape)
        padder = vtk.vtkImageConstantPad()
        padder.SetInputData(tomo_vtk)
        padder.SetConstant(0)
        padder.SetOutputWholeExtent(-1, tomo.shape[0], -1, tomo.shape[1], -1, tomo.shape[2])
        padder.Update()
        tomo_vtk = padder.GetOutput()

    # Flipping
    if flp is not None:
        flp_i = int(flp)
        if (flp_i >= 0) and (flp_i <= 3):
            fliper = vtk.vtkImageFlip()
            fliper.SetFilteredAxis(flp_i)
            fliper.SetInputData(tomo_vtk)
            fliper.Update()
            tomo_vtk = fliper.GetOutput()

    # Running Marching Cubes
    march.SetInputData(tomo_vtk)
    march.SetValue(0, th)
    march.Update()
    hold_poly = march.GetOutput()

    # Filtering
    hold_poly = poly_filter_triangles(hold_poly)

    # Normals orientation
    if normals is not None:
        orienter = vtk.vtkPolyDataNormals()
        orienter.SetInputData(hold_poly)
        orienter.AutoOrientNormalsOn()
        if normals == 'inwards':
            orienter.FlipNormalsOn()
        orienter.Update()
        hold_poly = orienter.GetOutput()

    if closed and (not is_closed_surface(hold_poly)):
        raise RuntimeError

    return hold_poly


def is_closed_surface(poly):
    """
    Checks if an input vtkPolyData is a closed surface
    :param poly: input vtkPolyData to check
    :return: True is the surface is closed, otherwise False
    """
    selector = vtk.vtkSelectEnclosedPoints()
    selector.CheckSurfaceOn()
    selector.SetSurfaceData(poly)
    if selector.GetCheckSurface() > 0:
        return True
    else:
        return False


def poly_filter_triangles(poly):
    """
    Filter a vtkPolyData to keep just the polys which are triangles
    :param poly: input vtkPolyData
    :return: a copy of the input poly but filtered
    """
    cut_tr = vtk.vtkTriangleFilter()
    cut_tr.SetInputData(poly)
    cut_tr.PassVertsOff()
    cut_tr.PassLinesOff()
    cut_tr.Update()
    return cut_tr.GetOutput()


def numpy_to_vti(array, spacing=[1, 1, 1]):
    """
    Converts a 3D numpy array into vtkImageData object
    :param array: 3D numpy array
    :param spacing: distance between pixels
    :return: a vtkImageData object
    """

    # Flattern the input array
    array_1d = numpy_support.numpy_to_vtk(num_array=np.reshape(array, -1, order='F'), deep=True, array_type=vtk.VTK_FLOAT)

    # Create the new vtkImageData
    nx, ny, nz = array.shape
    image = vtk.vtkImageData()
    image.SetSpacing(spacing)
    image.SetDimensions(nx, ny, nz)
    image.AllocateScalars(vtk.VTK_FLOAT, 1)
    image.GetPointData().SetScalars(array_1d)

    return image


def get_sub_copy(tomo, sub_pt, sub_shape):
    """
    Returns the a subvolume of a tomogram from a center and a shape
    :param tomo: input tomogram
    :param sub_pt: subtomogram center point
    :param sub_shape: output subtomogram shape (all dimensions must be even)
    :return: a copy with the subvolume or a VOI
    """

    # Initialization
    nx, ny, nz = sub_shape[0], sub_shape[1], sub_shape[2]
    mx, my, mz = tomo.shape[0], tomo.shape[1], tomo.shape[2]
    mx1, my1, mz1 = mx - 1, my - 1, mz - 1
    hl_x, hl_y, hl_z = int(nx * .5), int(ny * .5), int(nz * .5)
    x, y, z = int(round(sub_pt[0])), int(round(sub_pt[1])), int(round(sub_pt[2]))

    # Compute bounding restriction
    # off_l_x, off_l_y, off_l_z = x - hl_x + 1, y - hl_y + 1, z - hl_z + 1
    off_l_x, off_l_y, off_l_z = x - hl_x, y - hl_y, z - hl_z
    # off_h_x, off_h_y, off_h_z = x + hl_x + 1, y + hl_y + 1, z + hl_z + 1
    off_h_x, off_h_y, off_h_z = x + hl_x, y + hl_y, z + hl_z
    dif_l_x, dif_l_y, dif_l_z = 0, 0, 0
    dif_h_x, dif_h_y, dif_h_z = nx, ny, nz
    if off_l_x < 0:
        # dif_l_x = abs(off_l_x) - 1
        dif_l_x = abs(off_l_x)
        off_l_x = 0
    if off_l_y < 0:
        # dif_l_y = abs(off_l_y) - 1
        dif_l_y = abs(off_l_y)
        off_l_y = 0
    if off_l_z < 0:
        # dif_l_z = abs(off_l_z) - 1
        dif_l_z = abs(off_l_z)
        off_l_z = 0
    if off_h_x >= mx:
        dif_h_x = nx - off_h_x + mx1
        off_h_x = mx1
    if off_h_y >= my:
        dif_h_y = ny - off_h_y + my1
        off_h_y = my1
    if off_h_z >= mz:
        dif_h_z = nz - off_h_z + mz1
        off_h_z = mz1

    # Make the subvolume copy
    hold_sv = np.zeros(shape=sub_shape, dtype=tomo.dtype)
    hold_sv[dif_l_x:dif_h_x, dif_l_y:dif_h_y, dif_l_z:dif_h_z] = tomo[off_l_x:off_h_x, off_l_y:off_h_y, off_l_z:off_h_z]

    return hold_sv


def insert_svol_tomo(svol, tomo, sub_pt, merge='max'):
    """
    Insert the content of a subvolume to a tomogram
    :param svol: input subvolume (or subtomogram)
    :param tomo: input tomogram that is going to be modified
    :param sub_pt: subvolume center point in the input tomogram
    :param merge: merging mode, valid: 'max' (default), 'min', 'sum' and 'insert'
    :return:
    """

    # Initialization
    sub_shape = svol.shape
    nx, ny, nz = sub_shape[0], sub_shape[1], sub_shape[2]
    mx, my, mz = tomo.shape[0], tomo.shape[1], tomo.shape[2]
    mx1, my1, mz1 = mx - 1, my - 1, mz - 1
    hl_x, hl_y, hl_z = int(nx * .5), int(ny * .5), int(nz * .5)
    x, y, z = int(round(sub_pt[0])), int(round(sub_pt[1])), int(round(sub_pt[2]))

    # Compute bounding restriction
    # off_l_x, off_l_y, off_l_z = x - hl_x + 1, y - hl_y + 1, z - hl_z + 1
    off_l_x, off_l_y, off_l_z = x - hl_x, y - hl_y, z - hl_z
    # off_h_x, off_h_y, off_h_z = x + hl_x + 1, y + hl_y + 1, z + hl_z + 1
    off_h_x, off_h_y, off_h_z = x + hl_x, y + hl_y, z + hl_z
    dif_l_x, dif_l_y, dif_l_z = 0, 0, 0
    dif_h_x, dif_h_y, dif_h_z = nx, ny, nz
    if off_l_x < 0:
        # dif_l_x = abs(off_l_x) - 1
        dif_l_x = abs(off_l_x)
        off_l_x = 0
    if off_l_y < 0:
        # dif_l_y = abs(off_l_y) - 1
        dif_l_y = abs(off_l_y)
        off_l_y = 0
    if off_l_z < 0:
        # dif_l_z = abs(off_l_z) - 1
        dif_l_z = abs(off_l_z)
        off_l_z = 0
    if off_h_x >= mx:
        dif_h_x = nx - off_h_x + mx1
        off_h_x = mx1
    if off_h_y >= my:
        dif_h_y = ny - off_h_y + my1
        off_h_y = my1
    if off_h_z >= mz:
        dif_h_z = nz - off_h_z + mz1
        off_h_z = mz1
    if off_l_x > off_h_x:
        off_h_x = off_l_x
    if off_l_y > off_h_y:
        off_h_y = off_l_y
    if off_l_z > off_h_z:
        off_h_z = off_l_z
    if dif_l_x > dif_h_x:
        dif_h_x = dif_l_x
    if dif_l_y > dif_h_y:
        dif_h_y = dif_l_y
    if dif_l_z > dif_h_z:
        dif_h_z = dif_l_z
    sz_svol = [dif_h_x - dif_l_x, dif_h_y - dif_l_y, dif_h_z - dif_l_z]
    sz_off = [off_h_x - off_l_x, off_h_y - off_l_y, off_h_z - off_l_z]
    if (sz_svol[0] > sz_off[0]) and (sz_svol[0] > 1):
        dif_h_x -= 1
    if (sz_svol[1] > sz_off[1]) and (sz_svol[1] > 1):
        dif_h_y -= 1
    if (sz_svol[2] > sz_off[2]) and (sz_svol[2] > 1):
        dif_h_z -= 1

    # Modify the input tomogram
    if merge == 'insert':
        tomo[off_l_x:off_h_x, off_l_y:off_h_y, off_l_z:off_h_z] = svol[dif_l_x:dif_h_x, dif_l_y:dif_h_y,
                                                                  dif_l_z:dif_h_z]
    elif merge == 'sum':
        tomo[off_l_x:off_h_x, off_l_y:off_h_y, off_l_z:off_h_z] += svol[dif_l_x:dif_h_x, dif_l_y:dif_h_y,
                                                                   dif_l_z:dif_h_z]
    elif merge == 'min':
        tomo[off_l_x:off_h_x, off_l_y:off_h_y, off_l_z:off_h_z] = np.minimum(svol[dif_l_x:dif_h_x, dif_l_y:dif_h_y,
                                                                  dif_l_z:dif_h_z], tomo[off_l_x:off_h_x,
                                                                  off_l_y:off_h_y, off_l_z:off_h_z])
    elif merge == 'max':
        tomo[off_l_x:off_h_x, off_l_y:off_h_y, off_l_z:off_h_z] = np.maximum(svol[dif_l_x:dif_h_x, dif_l_y:dif_h_y,
                                                                  dif_l_z:dif_h_z], tomo[off_l_x:off_h_x,
                                                                  off_l_y:off_h_y, off_l_z:off_h_z])
    elif merge == 'and':
        tomo[off_l_x:off_h_x, off_l_y:off_h_y, off_l_z:off_h_z] = np.logical_and(svol[dif_l_x:dif_h_x, dif_l_y:dif_h_y,
                                                                             dif_l_z:dif_h_z], tomo[off_l_x:off_h_x,
                                                                             off_l_y:off_h_y, off_l_z:off_h_z])


# Applies a linear mapping to the input array for getting an array in the specified range
def lin_map(array, lb=0, ub=1):
    """
    Applies a linear mapping to the input array for getting an array in the specified range
    :param array: input array to remap
    :param lb: lower output bound for gray values (default 0)
    :param ub: upper output bound for gray values (default 1)
    :return: the remapped array with gray values in range lb and ub
    """
    a = np.max(array)
    i = np.min(array)
    den = a - i
    if den == 0:
        return array
    m = (ub - lb) / den
    c = ub - m*a
    return m*array + c


def wrap_angle(ang, deg=True):
    """
    Wrap an angle to be expressed in range (-pi, pi] or (-180, 180]
    :param ang: input angle to wrap, it may also be an array
    :param deg: if True (default) the input angle is degrees, otherwise in radians
    :return: the angle value (or values) in the proper range
    """
    if deg:
        phase = ((-ang + 180.) % (2.0 * 180.) - 180.) * -1.0
    else:
        phase = ((-ang + np.pi) % (2.0 * np.pi) - np.pi) * -1.0
    return phase


def point_to_poly(point, normal=None, n_name='n_normal'):
    """
    Converts a point into a poly
    :param point: 3-tuple with point coordinates
    :param normal: 3-tuple with the normal to be associated as property (default None)
    :param n_name: name for the normal (default 'normal')
    :return: a vtpPolyData object
    """
    poly = vtk.vtkPolyData()
    p_points = vtk.vtkPoints()
    p_cells = vtk.vtkCellArray()
    p_points.InsertNextPoint(point)
    p_cells.InsertNextCell(1)
    p_cells.InsertCellPoint(0)
    poly.SetPoints(p_points)
    poly.SetVerts(p_cells)
    if normal is not None:
        p_norm = vtk.vtkFloatArray()
        p_norm.SetName(n_name)
        p_norm.SetNumberOfComponents(3)
        p_norm.InsertTuple(0, normal)
        poly.GetPointData().AddArray(p_norm)
    return poly


def density_norm(tomo, mask=None, inv=True):
    """
    Tomogram density normalization (I(x,y,z)-mean) / std)
    :param tomo: input tomogram
    :param mask: if None (default) the whole tomogram is used for computing the statistics otherwise just the masked region
    :param inv: if True the values are inverted (default)
    :return:
    """

    # Input parsing
    if mask is None:
        mask = np.ones(shape=tomo.shape, dtype=bool)

    # Inversion
    if inv:
        hold_tomo = -1. * tomo
    else:
        hold_tomo = tomo

    # Statistics
    stat_tomo = hold_tomo[mask>0]
    mn, st = stat_tomo.mean(), stat_tomo.std()

    # Histogram equalization
    tomo_out = np.zeros(shape=tomo.shape, dtype=np.float32)
    if st > 0:
        tomo_out = (hold_tomo-mn) / st
    else:
        print('WARNING (density_norm): standard deviation=' + str(st))

    return tomo_out


def trilin_interp(x, y, z, tomogram):
    """
    Trilinear interpolation of the value of a coordinate point within a tomogram
    :param x: x input coordinate
    :param y: y input coordinate
    :param z: z input coordinate
    :param tomogram: input ndarray with the scalar field
    :return: the value interpolated
    """

    # Input parsing
    assert isinstance(tomogram, np.ndarray) and len(tomogram.shape) == 3
    xc = int(math.ceil(x))
    yc = int(math.ceil(y))
    zc = int(math.ceil(z))
    xf = int(math.floor(x))
    yf = int(math.floor(y))
    zf = int(math.floor(z))
    assert (xc < tomogram.shape[0]) and (yc < tomogram.shape[1]) and (zc < tomogram.shape[2]) and \
            (xf >= 0) and (yf >= 0) and (zf >= 0)

    # Get neigbourhood values
    v000 = float(tomogram[xf, yf, zf])
    v100 = float(tomogram[xc, yf, zf])
    v010 = float(tomogram[xf, yc, zf])
    v001 = float(tomogram[xf, yf, zc])
    v101 = float(tomogram[xc, yf, zc])
    v011 = float(tomogram[xf, yc, zc])
    v110 = float(tomogram[xc, yc, zf])
    v111 = float(tomogram[xc, yc, zc])

    # Coordinates correction
    xn = x - xf
    yn = y - yf
    zn = z - zf
    x1 = 1 - xn
    y1 = 1 - yn
    z1 = 1 - zn

    # Interpolation
    return (v000 * x1 * y1 * z1) + (v100 * xn * y1 * z1) + (v010 * x1 * yn * z1) + \
           (v001 * x1 * y1 * zn) + (v101 * xn * y1 * zn) + (v011 * x1 * yn * zn) + \
           (v110 * xn * yn * z1) + (v111 * xn * yn * zn)


def nn_iterp(x, y, z, tomogram):
    """
    Nearest neighbour interpolation of the value of a coordinate point within a tomogram
    :param x: x input coordinate
    :param y: y input coordinate
    :param z: z input coordinate
    :param tomogram: input ndarray with the scalar field
    :return: the value interpolated
    """

    # Input parsing
    assert isinstance(tomogram, np.ndarray) and len(tomogram.shape) == 3
    xc = int(math.ceil(x))
    yc = int(math.ceil(y))
    zc = int(math.ceil(z))
    xf = int(math.floor(x))
    yf = int(math.floor(y))
    zf = int(math.floor(z))
    assert (xc < tomogram.shape[0]) and (yc < tomogram.shape[1]) and (zc < tomogram.shape[2]) and \
               (xf >= 0) and (yf >= 0) and (zf >= 0)

    # Finding the closest voxel
    point = np.asarray((x, y, z))
    X, Y, Z = np.meshgrid(range(xf,xc+1), range(yf,yc+1), range(zf,zc+1), indexing='ij')
    X, Y, Z = X.flatten(), Y.flatten(), Z.flatten()
    min_point = np.asarray((X[0], Y[0], Z[0]))
    hold = point - min_point
    min_dist = np.sqrt((hold * hold).sum())
    for i in range(1, len(X)):
        hold_point = np.asarray((X[i], Y[i], Z[i]))
        hold = point - hold_point
        hold_dist = np.sqrt((hold * hold).sum())
        if hold_dist < min_dist:
            min_point = hold_point
            min_dist = hold_dist

    # Interpolation
    return tomogram[min_point[0], min_point[1], min_point[2]]


def poly_threshold(poly, p_name, mode='points', low_th=None, hi_th=None):
    """
    Threshold a vtkPolyData according the values of a property
    :param poly: vtkPolyData to threshold
    :param p_name: property name for points
    :param mode: determines if the property is associated to points data 'points' (default) or 'cells'
    :low_th: low threshold value, default None then the minimum property value is assigned
    :hi_th: high threshold value, default None then the maximum property value is assigned
    :return: the threshold vtkPolyData
    """

    # Input parsing
    prop = None
    assert (mode == 'points') or (mode == 'cells')
    if mode == 'points':
        n_arrays = poly.GetPointData().GetNumberOfArrays()
        for i in range(n_arrays):
            if p_name == poly.GetPointData().GetArrayName(i):
                prop = poly.GetPointData().GetArray(p_name)
                break
    else:
        n_arrays = poly.GetCellData().GetNumberOfArrays()
        for i in range(n_arrays):
            if p_name == poly.GetCellData().GetArrayName(i):
                prop = poly.GetCellData().GetArray(p_name)
                break
    assert prop is not None
    if (low_th is None) or (hi_th is None):
        rg_low, rg_hi = prop.GetRange()
    if low_th is None:
        low_th = rg_low
    if hi_th is None:
        hi_th = rg_hi

    # Points thresholding filter
    th_flt = vtk.vtkThreshold()
    th_flt.SetInputData(poly)
    if mode == 'cells':
        th_flt.SetInputArrayToProcess(0, 0, 0, vtk.vtkDataObject.FIELD_ASSOCIATION_CELLS, p_name)
    else:
        th_flt.SetInputArrayToProcess(0, 0, 0, vtk.vtkDataObject.FIELD_ASSOCIATION_POINTS, p_name)
    # th_flt.ThresholdByUpper(.5)
    th_flt.ThresholdBetween(low_th, hi_th)
    th_flt.AllScalarsOff()
    th_flt.Update()

    surf_flt = vtk.vtkDataSetSurfaceFilter()
    surf_flt.SetInputData(th_flt.GetOutput())
    surf_flt.Update()

    return surf_flt.GetOutput()

def gen_six_connectivity_mask():
    """
    Generates a 6-connectivity mask
    :return: 3x3x3 boolean numpy array
    """
    mask = np.zeros(shape=(3, 3, 3), dtype=bool)
    mask[1, 1, 0] = True
    mask[0, 1, 1] = True
    mask[1, 1, 1] = True
    mask[2, 1, 1] = True
    mask[1, 0, 1] = True
    mask[1, 2, 1] = True
    mask[1, 1, 2] = True
    return mask


def clean_dir(dir):
    """
    Clean an directory contents (directory is preserved)
    :param dir: directory path
    """
    for root, dirs, files in os.walk(dir):
        for f in files:
            os.unlink(os.path.join(root, f))
        for d in dirs:
            shutil.rmtree(os.path.join(root, d))


def load_particles_list(in_path, delimiter=','):
    """
    Load particles data from an input CSV file and store them into files
    :param in_path: path to the input CSV file
    :param delimiter: delimiter for the CSV file (default ',')
    :return: a 4-tuple with, in this order, correlation, particle ids, coordinates and rotations
    """
    corrs, part_ids, coords, rots = list(), list(), list(), list()
    with open(in_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=delimiter)
        for row in reader:
            if 'correlation' in row.keys():
                try:
                    corrs.append(float(row['correlation']))
                except ValueError:
                    try:
                        corrs.append(float(row['correlation'].replace(',','.')))
                    except ValueError:
                        corrs.append(-2)
            else:
                corrs.append(-2)
            try:
                part_ids.append(row['class'])
            except KeyError:
                part_ids.append('-')
            try:
                coords.append(np.asarray((row['x'], row['y'], row['z']), dtype=float))
            except ValueError:
                coords.append(np.asarray((row['x'].replace(',','.'), row['y'].replace(',','.'),
                                          row['z'].replace(',','.')), dtype=float))
            if 'z1' in row.keys() and 'x1' in row.keys() and 'z2' in row.keys():
                if (row['z1'] == 'NaN') or (row['x1'] == 'NaN') or (row['z2'] == 'NaN'):
                    rots.append(np.asarray((1., .0, .0, .0)))  # Neutral unit-quaternion element
                else:
                    rots.append(affine.zxz_to_quat(float(row['z1']), float(row['x1']), float(row['z2']),
                                                   extrinsic=True, method='direct'))
            else:
                try:
                    rot = np.asarray((row['quat0'], row['quat1'], row['quat2'], row['quat3']), dtype=float)
                except ValueError:
                    rot = np.asarray((row['quat0'].replace(',','.'), row['quat1'].replace(',','.'),
                                      row['quat2'].replace(',','.'), row['quat3'].replace(',','.')), dtype=float)
                except KeyError:
                    rot = np.asarray((1, 0, 0, 0), dtype=float)
                if np.isnan(rot).sum() > 0:
                    rots.append(np.asarray((1., .0, .0, .0))) # Neutral unit-quaternion element
                else:
                    rots.append(rot)
    return corrs, part_ids, coords, rots


def coords_scale_supression(coords, scale, weights=None, filter=False):
    """
    Coordinates suppression to ensure a minimum euclidean distance among them, it returns a list
    with the indices of the coordinates to delete or directly filter the input coordinates list ('filter' option)
    :param coords: iterable of coordinates
    :param scale: scale suppression (euclidean distance)
    :param weights: array with the points weights of every coordinate to give priorities (default None)
    :param filter: if True (default False) the input list of coordinates is filtered and returned
    :return: a list with the indices of the coordinates to delete or directly filter the input coordinates list
    ('filter' option)
    """

    # Initialization
    del_l = list()
    del_lut = np.zeros(shape=len(coords), dtype=np.bool)

    coords = np.asarray(coords, dtype=np.float32)
    if weights is None:
        s_ids = np.arange(len(coords))
    else:
        s_ids = np.argsort(weights)[::-1]

    # Coordinates loop
    for s_id in s_ids:
        # Not process already deleted coords
        if not del_lut[s_id]:
            eu_dsts = coords[s_id, :] - coords
            eu_dsts = np.sqrt((eu_dsts * eu_dsts).sum(axis=1))
            # Finding closest points
            n_ids = np.where(eu_dsts < scale)[0]
            # Add to deletion list
            for idx in n_ids:
                if (idx != s_id) and (not del_lut[idx]):
                    del_l.append(idx)
                    del_lut[idx] = True

    if filter:
        hold_coords = list()
        for i in range(del_lut.shape[0]):
            if not del_lut[i]:
                hold_coords.append(coords[i, :])
        return hold_coords
    else:
        return del_l