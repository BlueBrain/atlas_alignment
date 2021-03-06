"""A collection of synchronizations related to working with Allen's API.

Notes
-----
See the module `atlalign.allen.utils.py` for lower level functions that are called within this module.
"""

"""
    The package atlalign is a tool for registration of 2D images.

    Copyright (C) 2021 EPFL/Blue Brain Project

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import numpy as np
import requests
from skimage.transform import resize, warp

from atlalign.allen.utils import (
    get_2d,
    get_2d_bulk,
    get_3d,
    get_image,
    pir_to_xy_API_single,
    xy_to_pir_API_single,
)
from atlalign.base import DisplacementField


def get_reference_image(p, folder=None):
    """Get a given coronal slice image for the fundamental atlas of reference space 9.

    Notes
    -----
    What is this atlas?
        - 602630314

    What is the dataset id?
        - 576985993

    What is the coronal section thickness of this dataset?
        - 10 microns

    How many coronal sections are there?
        - 1320

    What is the resolution of section images?
        - (8000, 11400)

    Why is it special?
        - Both all the 2d and 3d matrices are identities

    How was it made?
        - Some average of many coronal section.

    Parameters
    ----------
    p : int
        Coronal slice coordinate in microns. Note that p = section_thickness * section_number. So in our case
        p = 10 * section number.

    folder : str or LocalPath or None
        Local folder where image saved. If None then automatically defaults to `CACHE_FOLDER`.

    Returns
    -------
    img : np.ndarray
        An image of shape (8000, 11400, 3). The dtype is np.uint8.

    folder : str or LocalPath or None
        Local folder where image saved. If None then automatically defaults to `CACHE_FOLDER`.

    """
    if p % 10 != 0:
        raise ValueError(
            "p must be divisible by 10 (distances are spaced by 10 microns)"
        )

    section_data_set_id = 576985993
    section_number = p // 10

    url = "http://api.brain-map.org/api/v2/data/query.json?"
    url += "criteria=model::SectionImage,rma::criteria,"
    url += "[section_number$eq{}],section_data_set[id$eq{}]".format(
        section_number, section_data_set_id
    )
    r = requests.get(url)

    if r.status_code != 200:
        raise ValueError("Request failed.")

    raw = r.json()["msg"]

    if not raw:
        raise ValueError("No entries for the query.")

    id_ = raw[0]["id"]

    return get_image(id_, folder)


def xy_to_pir_API(x_list, y_list, image_id):
    """Convert xs and ys from the section image into ps, is, rs in the reference space using the API.

    Notes
    -----
    The reference space is always uniquely determined by the dataset the image comes from.

    Parameters
    ----------
    x_list : list
        List of x coordinates (columns) in the section image with id `image_id`.

    y_list : list
        List of y coordinates (rows) in the section image with id `image_id`.

    image_id : int
        Integer representing an id of the section image with id `image_id`.


    Returns
    -------
    p_list: list
        List of corresponding coronal dimensions (anterior -> posterior).

    i_list : list
        List of corresponding transversal dimensions (superior -> inferior). The y (row) coordinate in coronal sections.

    r_list : list
        List of corresponding sagittal dimensions (left -> right). The  x (column) coordinate in coronal sections.


    Raises
    ------
    TypeError
        If `x_list` or `y_list` not lists.

    ValueError:
        If `x_list` and `y_list` different length.

    """
    # Checks
    if not isinstance(x_list, list) and not isinstance(y_list, list):
        raise TypeError("The x_list and y_list need to be lists")

    if len(x_list) != len(y_list):
        raise ValueError("The inputs x_list and y_list need to have the same length.")

    p_list, i_list, r_list = [], [], []

    for x, y in zip(x_list, y_list):
        p, i, r = xy_to_pir_API_single(x, y, image_id=image_id)

        p_list.append(p)
        i_list.append(i)
        r_list.append(r)

    return p_list, i_list, r_list


def pir_to_xy_API(p_list, i_list, r_list, dataset_id, reference_space=9):
    """Convert an ps, is, rs in a reference space into a xs, ys in images of the dataset using API.

    Parameters
    ----------
    p_list : list
        List of coronal dimensions (anterior -> posterior).

    i_list : list
        List of transversal dimensions (superior -> inferior). The y (row) coordinate in coronal sections.

    r_list : list
        List of sagittal dimensions (left -> right). The  x (column) coordinate in coronal sections.

    dataset_id : int
        Id of the section dataset.

    reference_space : int, optional
        Reference space for which to perform the computations, most likely 9 is the one we always want.

    Returns
    -------
    x_list : list
        Corresponding list of x coordinates (columns) in the section images listed in `closest_section_image_id_list`.

    y_list : list
        Corresponding list of y coordinates (rows) in the section image with id `image_id`.


    section_number_list : list
        List of section numbers as calculated by the 3D transformation. Since the dataset will never contain exactly
        this section one just uses the closest section image (see `closest_section_image_id_list`).

    closest_section_image_id_list : list
        List of ids of images contained in the section dataset such that for the for the given `p`, `i`, `r` input
        is the closest existing approximation.

    """
    # Checks
    if not (
        isinstance(p_list, list)
        and isinstance(i_list, list)
        and isinstance(r_list, list)
    ):
        raise TypeError("The p_list, i_list and r_list need to be lists")

    if not (len(p_list) == len(i_list) == len(r_list)):
        raise ValueError(
            "The inputs p_list, i_list and r_list need to have the same length."
        )

    x_list, y_list, section_number_list, closest_section_image_id_list = [], [], [], []

    for p, i, r in zip(p_list, i_list, r_list):
        x, y, section_number, closest_section_image_id = pir_to_xy_API_single(
            p, i, r, dataset_id=dataset_id, reference_space=reference_space
        )

        x_list.append(x)
        y_list.append(y)
        section_number_list.append(section_number)
        closest_section_image_id_list.append(closest_section_image_id)

    return x_list, y_list, section_number_list, closest_section_image_id_list


def pir_to_xy_local(p_list, i_list, r_list, dataset_id, reference_space=9):
    """Convert an ps, is, rs in a reference space into a xs, ys in images of the dataset.

    Notes
    -----
    The speed up here is not sufficient because we allow for different coronal slices with each query.


    Parameters
    ----------
    p_list : list
        List of coronal dimensions (anterior -> posterior).

    i_list : list
        List of transversal dimensions (superior -> inferior). The y (row) coordinate in coronal sections.

    r_list : list
        List of sagittal dimensions (left -> right). The  x (column) coordinate in coronal sections.

    dataset_id : int
        Id of the section dataset.

    reference_space : int, optional
        Reference space for which to perform the computations, most likely 9 is the one we always want.

    Returns
    -------
    x_list : list
        Corresponding list of x coordinates (columns) in the section images listed in `closest_section_image_id_list`.

    y_list : list
        Corresponding list of y coordinates (rows) in the section image with id `image_id`.


    section_number_list : list
        List of section numbers as calculated by the 3D transformation. Since the dataset will never contain exactly
        this section one just uses the closest section image (see `closest_section_image_id_list`).

    closest_section_image_id_list : list
        List of ids of images contained in the section dataset such that for the for the given `p`, `i`, `r` input
        is the closest existing approximation.

    """
    # Check dimensions
    if not (
        isinstance(i_list, list)
        and isinstance(r_list, list)
        and isinstance(p_list, list)
    ):
        raise TypeError("Both the i_list and r_list need to be lists.")

    if not len(p_list) == len(i_list) == len(r_list):
        raise ValueError("The i_list and r_list need to have the same length.")

    else:
        N = len(p_list)

    # Get dataset metadata
    a_3d, reference_space_actual, section_thickness = get_3d(
        dataset_id=dataset_id,
        ref2inp=True,  # pir_to_xy = ref2inp
        add_last=True,
        return_meta=True,
    )

    # Check that reference space is 9
    if not reference_space_actual == reference_space == 9:
        raise NotImplementedError("Currently only reference_space 9 allowed")

    # Get bulk section metadata (keys are section_ids and values are tuples (a_2d, section_number))
    sections_bulk = get_2d_bulk(dataset_id=dataset_id, ref2inp=True, add_last=True)

    # Define helpers
    section_number_to_id = {v[1]: k for k, v in sections_bulk.items()}
    section_number_to_a = {
        k: sections_bulk[v][0] for k, v in section_number_to_id.items()
    }

    existing_section_numbers = sorted(list(section_number_to_id.keys()))

    # Perform multiplication
    data_matrix_3d = np.vstack((p_list, i_list, r_list, np.ones((1, N))))

    res = np.dot(a_3d, data_matrix_3d)[:3, :]  # remove homogeneous coordinates
    section_numbers = res[2, :] / section_thickness

    # Start populating
    x_list, y_list, section_number_list, closest_section_image_id_list = [], [], [], []

    for i in range(N):
        # Unfortunately needs to be done separately for each coordinate

        # Get section and section_image_id from the first coordinates
        closest_section_number = min(
            existing_section_numbers, key=lambda x: abs(x - section_numbers[i])
        )
        closest_section_image_id = section_number_to_id[closest_section_number]

        a_2d = section_number_to_a[closest_section_number]

        data_matrix_2d = np.vstack((res[:2, [i]], [1]))  # add homogeneous
        overall_res = np.dot(a_2d, data_matrix_2d)[:2]

        x_list.append(overall_res[0])
        y_list.append(overall_res[1])
        section_number_list.append(closest_section_number)
        closest_section_image_id_list.append(closest_section_image_id)

    return x_list, y_list, section_number_list, closest_section_image_id_list


def pir_to_xy_local_coronal(p, i_list, r_list, dataset_id, reference_space=9):
    """Convert a fixed p and custom is, rs in a reference space into a xs, ys in images of the dataset.

    Notes
    -----
    The difference here is that we only allow 1 image_section. This will make things significantly quicker
    since we do not need to extract a separate 2D transformation for each (p, i, r).


    Parameters
    ----------
    p : float
        A fixed coronal dimensions (anterior -> posterior). In microns.

    i_list : list
        List of transversal dimensions (superior -> inferior). The y (row) coordinate in coronal sections.

    r_list : list
        List of sagittal dimensions (left -> right). The  x (column) coordinate in coronal sections.

    dataset_id : int
        Id of the section dataset.

    reference_space : int, optional
        Reference space for which to perform the computations, most likely 9 is the one we always want.

    Returns
    -------
    x_list : list
        Corresponding list of x coordinates (columns) in the section images listed in `closest_section_image_id_list`.

    y_list : list
        Corresponding list of y coordinates (rows) in the section image with id `image_id`.


    section_number : int
        Section number as computed by the 3D transformation. Since the dataset will never contain exactly
        this section one just uses the closest section image (see `closest_section_image_id`).

    closest_section_image_id : int
        Id of the image contained in the section dataset such that for the for the given `p`, `i`, `r` input
        is the closest existing approximation.

    """
    # Check dimensions

    if not (isinstance(i_list, list) and isinstance(r_list, list)):
        raise TypeError("Both the i_list and r_list need to be lists.")

    if not len(i_list) == len(r_list):
        raise ValueError("The i_list and r_list need to have the same length.")

    else:
        N = len(i_list)

    p_list = p if isinstance(p, list) else [p] * N

    if len(p_list) != N:
        raise ValueError("The p_list, i_list and r_list need to have the same length.")

    # Get dataset metadata
    a_3d, reference_space_actual, section_thickness = get_3d(
        dataset_id=dataset_id,
        ref2inp=True,  # pir_to_xy = ref2inp
        add_last=True,
        return_meta=True,
    )

    # Check that reference space is 9
    if not reference_space_actual == reference_space == 9:
        raise NotImplementedError("Currently only reference_space 9 allowed")

    # Determine corresponding section images in the corners
    section_number_corner_mode, image_id_corner_mode = corners_rs9(p, dataset_id)

    a_2d = get_2d(image_id=image_id_corner_mode, ref2inp=True, add_last=True)

    # Perform multiplication
    data_matrix_3d = np.vstack((p_list, i_list, r_list, np.ones((1, N))))

    res = np.dot(a_3d, data_matrix_3d)[:3, :]  # remove homogeneous coordinates

    data_matrix_2d = np.vstack((res[:2], np.ones(N)))
    overall_res = np.dot(a_2d, data_matrix_2d)[:2]

    return (
        list(overall_res[0]),
        list(overall_res[1]),
        section_number_corner_mode,
        image_id_corner_mode,
    )


def corners_rs9(p, dataset_id):
    """Determine the most suitable section image based on 4 corners of reference space 9.

    Parameters
    ----------
    p : int
        Coronal slice coordinate in microns. Note that p = section_thickness * section_number. So in our case
        p = 10 * section number.

    dataset_id : int
        Id of the section dataset.


    Returns
    -------
    section_number : int
        Section number as computed by the 3D transformation. Since the dataset will never contain exactly
        this section one just uses the closest section image (see `closest_section_image_id`).

    closest_section_image_id : int
        Id of the image contained in the section dataset such that for the for the given `p`, `i`, `r` input
        is the closest existing approximation.

    """
    _, _, section_number_corners, image_id_corners = pir_to_xy_API(
        4 * [p],
        [0, 7999, 0, 7999],
        [0, 0, 11399, 11399],
        dataset_id=dataset_id,
        reference_space=9,
    )

    # Find mode
    section_number_corner_mode = max(
        set(section_number_corners), key=section_number_corners.count
    )  # if multimodal, then lower is chosen

    image_id_corner_mode = image_id_corners[
        section_number_corners.index(section_number_corner_mode)
    ]

    return section_number_corner_mode, image_id_corner_mode


def warp_rs9(
    p,
    dataset_id,
    ds_f=1,
    invert_colors=False,
    allow_resizing=True,
    img_section_id=None,
    skip_reference=False,
):
    """Given a fixed coronal section, map the closest section image of the dataset into CCF.

    Parameters
    ----------
    p : int
        Coronal slice coordinate in microns. Note that p = section_thickness * section_number. So in our case
        p = 10 * section number.

    dataset_id : int
        Id of the section dataset.

    ds_f : int, optional
        Downsampling factor. If set to 1 no downsampling takes place. Note that if `ds_f` = 25, then
        we obtain the shape (320, 456).

    invert_colors : bool, optional
        If True, then img_section = 255 - img_section.

    allow_resizing : bool, optional
        If True, then both the reference and section image are simply resized via `skimage.transform.resize`.
        It allows us to see how simple resizing compares to sophisticated warping. Note that sometimes
        the function gets stuck for large images and that is why this boolean is introduced.

    img_section_id : None or int
        If None then using corners technique to find. Otherwise just use the passed one.

    skip_reference : bool
        If True, then not downloading the reference image.

    Returns
    -------
    img_ref_resized : np.array or None
        Image of shape (8000 // `ds_f`, 11400 // `ds_f`, ?) representing the resized reference image.
        If `allow_resizing` == False then equals None.

    img_section_resized : np.array or None
        Image of shape (8000 // `ds_f`, 11400 // `ds_f`, ?) representing the resized section image.
        If `allow_resizing` == False then equals None.

    warped_section_image : np.array
        Image of shape (8000 // `ds_f`, 11400 // `ds_f`, ?) representing the warped section image.

    """

    def transformation(coords):
        """Transform from (r, y) to (x, y).

        Notes
        -----
        Warp of scikit-image is always using the convention that coords = (columns, rows). So for our inputs
        this means (r, i) and output (x, y).

        Parameters
        ----------
        coords : np.array, shape = (N, 2)
            (r, i) coordinates.

        Returns
        -------
        output_coords : np.array, shape = (N, 2)
            (x, y) coordinates.

        """
        i_list = list(coords[:, 1] * ds_f)
        r_list = list(coords[:, 0] * ds_f)

        output_coords = np.empty_like(coords)

        x_list, y_list, _, _ = pir_to_xy_local_coronal(
            p, i_list, r_list, dataset_id=dataset_id
        )

        output_coords[:, 1] = y_list
        output_coords[:, 0] = x_list

        return output_coords

    # Variables
    if img_section_id is None:
        _, img_section_id = corners_rs9(p, dataset_id)
    output_shape = (8000 // ds_f, 11400 // ds_f)

    # Images
    img_ref = get_reference_image(p) if not skip_reference else None
    img_section = get_image(img_section_id)

    if invert_colors:
        img_section = 255 - img_section  # Assumes that dtype of img_section is uint8

    # Computations
    img_ref_resized = (
        resize(img_ref, output_shape)
        if (allow_resizing and not skip_reference)
        else None
    )
    img_section_resized = resize(img_section, output_shape) if allow_resizing else None
    warped_img_section = warp(
        img_section, inverse_map=transformation, output_shape=output_shape
    )

    return img_ref_resized, img_section_resized, warped_img_section


def get_transform(p, dataset_id, ds_f=1):
    """Get transformation given a fixed coronal section.

    Parameters
    ----------
    p : int
        Coronal slice coordinate in microns.

    dataset_id : int
        Id of the section dataset. Used to determine the 3D matrix.

    ds_f : int, optional
        Downsampling factor. If set to 1 no downsampling takes place. Note that if `ds_f` = 25, then
        we obtain the shape (320, 456).

    Returns
    -------
    df : DisplacementField
        Displacement field of shape (8000 // `ds_f`, 11400 // `ds_f`, ?) representing reference -> moved transformation.

    """
    output_shape = (8000 // ds_f, 11400 // ds_f)

    y, x = np.indices(output_shape)
    grid = np.stack((x.ravel(), y.ravel())).T

    i_list = list(grid[:, 1] * ds_f)
    r_list = list(grid[:, 0] * ds_f)

    output_grid = np.empty_like(grid)

    x_list, y_list, _, _ = pir_to_xy_local_coronal(
        p, i_list, r_list, dataset_id=dataset_id
    )

    output_grid[:, 1] = y_list
    output_grid[:, 0] = x_list

    df = DisplacementField.from_transform(
        output_grid[:, 0].reshape(output_shape), output_grid[:, 1].reshape(output_shape)
    )

    return df


def download_dataset(
    dataset_id,
    ds_f=25,
    p_detection_xy=(0, 0),
    order="sn",
    verbose=True,
    include_expression=False,
):
    """Download entire dataset.

    Parameters
    ----------
    dataset_id : int
        Id of the section dataset. Used to determine the 3D matrix.

    ds_f : int, optional
        Downsampling factor. If set to 1 no downsampling takes place. Note that if `ds_f` = 25, then
        we obtain the shape (320, 456).

    p_detection_xy : tuple
        Represents the x and y coordinate in the image that will be used for determining the coronal dimension `p`
        in the reference space.

    order : str, {'id', 'sn'}
        How to order the streamed pairs.
            - 'id' : smallest image ids first
            - 'sn' : highest section number (equivalent to lowest p becase AB switched the order:) first

    verbose : bool
        If True, then printing information to standard output.

    include_expression : bool
        If True then the generator returns 5 objects where the last one is the expression image.

    Returns
    -------
    res_dict : generator
        Generator yielding consecutive four tuples of  (image_id, p, img, df). The `p` is the coronal dimension in
        microns. The `img` is the raw gene expression image with dtype `uint8`. The `df` is the displacement field of
        shape (8000 // `ds_f`, 11400 // `ds_f`). Note that the sorting. If `include_expression=True` then last
        returned image is the processed expression image. That is the generator yield (image_id, p, img, df, img_expr).
    """
    metadata = get_2d_bulk(dataset_id)

    if order == "id":
        all_image_ids = sorted(list(metadata.keys()))

    elif order == "sn":
        all_image_ids = sorted(list(metadata.keys()), key=lambda x: -metadata[x][1])

    else:
        raise ValueError("Unsupported order {}".format(order))

    for image_id in all_image_ids:
        if verbose:
            print(image_id)
        try:
            p, _, _ = xy_to_pir_API_single(*p_detection_xy, image_id=image_id)
            img = get_image(image_id)
            df = get_transform(p, dataset_id=dataset_id, ds_f=ds_f)

            if not include_expression:
                yield image_id, p, img, df
            else:
                img_expression = get_image(image_id, expression=True)
                yield image_id, p, img, df, img_expression

        except Exception as e:
            print(e)
            if not include_expression:
                yield image_id, None, None, None
            else:
                yield image_id, None, None, None, None
