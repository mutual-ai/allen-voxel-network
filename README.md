allen-voxel-network
===================

Tools for working with Allen Institute for Brain Science voxel-scale 
connectivity data.

Requirements:
* numpy
* scipy
* h5py
* allensdk

To fit connectomes:
* [spatial-network-regression](https://github.com/kharris/spatial-network-regression)

Generating a voxel linear model
-------------------------------

1. Edit `run_setup.py`. This sets which structures will be
   included, the values of the regularization parameter, etc.
2. `python create_visual_matrices.py`. This will create a hierarchy of 
   directories for model fitting with nested cross-validation.
3. Run the commands in `model_fitting_cmds` (located in the project directory) 
   to perform the model fits.
4. Run `python model_select_and_fit.py`. In the inner cross-validation loop,
   evaluate the errors and perform model selection.
5. Run the commands in `model_fitting_after_selection_cmds`. This will fit the
   selected models.
6. Run `python region_model_fits_and_voxel_errors.py`. This will both evaluate
   the errors of the voxel models as well as fit regional models and compare
   their errors to the voxel models.

Visualizing voxel model
-----------------------

1. Run `python voxel_model_visualizations.py`. This performs fake injections
   into VISp, plotting the results. Also saves volumetric data & region 
   labeled plot.
2. You can turn the virtual injection pictures into a movie easily: 
`avconv -q 4 -r 7 -b 9600 -i int_virt_inj%d.png movie.mp4`
3. You can visualize the volumetric data in VTK format (.vti files). Use
   [Paraview](http://www.paraview.org/).

Generating a regional model
---------------------------

First edit the following scripts to set the data and output directories, then
run:

     python create_regional_matrices.py
     python run_new_regional_model.py

If you want to compare the output of this model to that from Oh et al. (2014),
this can be accomplished with `compare_new_old.py`.

