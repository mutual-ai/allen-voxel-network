# Kameron Decker Harris
# modified from code by Nicholas Cain

def pickle(data, file_name):
    import pickle as pkl    
    f=open(file_name, "wb")
    pkl.dump(data, f)
    f.close()

def unpickle(file_name):
    import pickle as pkl
    f=open(file_name, "rb")
    data=pkl.load(f)
    f.close()
    return data

def write_dictionary_to_group(group, dictionary, create_name = None):
    if create_name != None:
        group = group.create_group(create_name)
    for key, val in dictionary.items():
        group[str(key)] = val
    return

def read_dictionary_from_group(group):
    dictionary = {}
    for name in group:
        dictionary[str(name)] = group[name].value
    return dictionary

def generate_region_matrices(data_dir,
                             source_id_list, target_id_list, 
                             min_voxels_per_injection = 50,
                             LIMS_id_list = None, source_shell=False):
    '''
    Generates the source and target expression matrices for a set of
    injections, which can then be used to fit the linear model, etc.

    Modified from mesoscale_connectivity_linear_model by Nicholas Cain

    Parameters
    ==========
      data_dir: directory containing hdf5 files
      source_id_list: source structure ids to consider
      target_id_list: target structure ids to consider
      min_voxels_per_injection, default=50
      LIMS_id_list: list of experiments to include
      source_shell, default=False: whether to use mask which draws a shell
        around source regions to account for extent of dendrites
        
    Returns
    =======
      experiment_dict, with fields 'experiment_source_matrix',
        'experiment_target_matrix_ipsi', 'experiment_target_matrix_contra',
        'col_label_list_source', 'col_label_list_target', 'row_label_list'
    '''
    from friday_harbor.structure import Ontology
    from friday_harbor.mask import Mask
    from friday_harbor.experiment import ExperimentManager
    import numpy as np
    import warnings
    
    EM=ExperimentManager(data_dir=data_dir)
    ontology=Ontology(data_dir=data_dir)

    if LIMS_id_list == None:
        ex_list=EM.all()
        LIMS_id_list=[e.id for e in ex_list]
    else:
        ex_list=[EM.experiment_by_id(LIMS_id) for LIMS_id in LIMS_id_list]
    
    # Get the injection masks
    PD_dict={}
    injection_mask_dict={}
    injection_mask_dict_shell={}
    for e in ex_list:
        curr_LIMS_id=e.id
        PD_dict[curr_LIMS_id]=e.density()
        injection_mask_dict[curr_LIMS_id]=e.injection_mask()
        if source_shell == True:
            injection_mask_dict_shell[curr_LIMS_id]=e.injection_mask(shell=True)
    
    # Get the region masks
    region_mask_dict={}
    region_mask_ipsi_dict={}
    region_mask_contra_dict={}
    for curr_structure_id in source_id_list + target_id_list:
        region_mask_dict[curr_structure_id]=ontology.get_mask_from_id_nonzero(curr_structure_id)
        region_mask_ipsi_dict[curr_structure_id]=ontology.get_mask_from_id_right_hemisphere_nonzero(curr_structure_id)
        region_mask_contra_dict[curr_structure_id]=ontology.get_mask_from_id_left_hemisphere_nonzero(curr_structure_id)

    def get_integrated_PD(curr_LIMS_id, intersection_mask):
        def safe_sum(values):
            sum=0.0
            for val in values:
                if val == -1:
                    val=0.0
                elif val == -2:
                    warnings.warn(('projection density error -2, ',
                                   'missing tile in LIMS experiment %d')
                                  % curr_LIMS_id)
                    val=0.0
                elif val == -3:
                    warnings.warn(('projection density error -3, ',
                                   'no data in LIMS experiment %d')
                                  % curr_LIMS_id)
                    val=0.0
                sum+=val
            return sum
        if len(intersection_mask) > 0:
            curr_sum=safe_sum(PD_dict[curr_LIMS_id][intersection_mask.mask])
        else:
            curr_sum=0.0
        return curr_sum
    
    # Initialize matrices:
    structures_above_threshold_ind_list=[]
    experiment_source_matrix_pre=np.zeros((len(LIMS_id_list), 
                                             len(source_id_list)))
    
    # Source:
    for jj, curr_structure_id in enumerate(source_id_list):
        # Get the region mask:
        curr_region_mask=region_mask_dict[curr_structure_id]
        ipsi_injection_volume_list=[]
        for ii, curr_LIMS_id in enumerate(LIMS_id_list):
            # Get the injection mask:
            curr_experiment_mask=injection_mask_dict[curr_LIMS_id]
            # Compute integrated density, source:
            intersection_mask=Mask.intersection(curr_experiment_mask, curr_region_mask)
            experiment_source_matrix_pre[ii, jj]=get_integrated_PD(curr_LIMS_id, intersection_mask)
            ipsi_injection_volume_list.append(len(intersection_mask)) 
    
        # Determine if current structure should be included in source list:
        ipsi_injection_volume_array=np.array(ipsi_injection_volume_list)
        num_exp_above_thresh=len(np.nonzero(ipsi_injection_volume_array 
                                            >= min_voxels_per_injection)[0])
        if num_exp_above_thresh > 0:
            structures_above_threshold_ind_list.append(jj)
            
    # Determine which experiments should be included:
    expermiments_with_one_nonzero_structure_list=[] 
    for ii, row in enumerate(experiment_source_matrix_pre):
        if row.sum() > 0.0:
            expermiments_with_one_nonzero_structure_list.append(ii)

    if len(structures_above_threshold_ind_list) < len(source_id_list):
        raise Exception('length of structures_above_threshold_ind_list < source_id_list')
    
    experiment_source_matrix=experiment_source_matrix_pre[:,structures_above_threshold_ind_list][expermiments_with_one_nonzero_structure_list,:]
    row_label_list=np.array(LIMS_id_list)[expermiments_with_one_nonzero_structure_list]
    col_label_list_source=np.array(source_id_list)[structures_above_threshold_ind_list]
     
    # Target:
    experiment_target_matrix_ipsi=np.zeros((len(row_label_list), 
                                            len(target_id_list)))
    experiment_target_matrix_contra=np.zeros((len(row_label_list), 
                                              len(target_id_list)))
    for jj, curr_structure_id in enumerate(target_id_list):
        # Get the region mask:
        curr_region_mask_ipsi=region_mask_ipsi_dict[curr_structure_id]
        curr_region_mask_contra=region_mask_contra_dict[curr_structure_id]
        
        for ii, curr_LIMS_id in enumerate(row_label_list):
            # Get the injection mask:
            if source_shell == True:
                curr_experiment_mask=injection_mask_dict_shell[curr_LIMS_id]
            else:
                curr_experiment_mask=injection_mask_dict[curr_LIMS_id]
            # Compute integrated density, target, ipsi:
            difference_mask=curr_region_mask_ipsi.difference(curr_experiment_mask)
            experiment_target_matrix_ipsi[ii, jj]=get_integrated_PD(curr_LIMS_id, 
                                                                    difference_mask)
            
            # Compute integrated density, target, contra:    
            difference_mask=curr_region_mask_contra.difference(curr_experiment_mask)
            experiment_target_matrix_contra[ii, jj]=get_integrated_PD(curr_LIMS_id, difference_mask) 

    # Include only structures with sufficient injection information, and 
    # experiments with one nonzero entry in row:
    experiment_dict={}
    experiment_dict['experiment_source_matrix']=experiment_source_matrix
    experiment_dict['experiment_target_matrix_ipsi']=experiment_target_matrix_ipsi
    experiment_dict['experiment_target_matrix_contra']=experiment_target_matrix_contra
    experiment_dict['col_label_list_source']=col_label_list_source 
    experiment_dict['col_label_list_target']=np.array(target_id_list)
    experiment_dict['row_label_list']=row_label_list 
    return experiment_dict

def region_laplacian(mask):
    '''
    Generate the laplacian matrix for a given region's voxels. This is the 
    graph laplacian of the neighborhood graph.

    Parameters
    ==========
      mask

    Returns
    =======
      L: num voxel x num voxel laplacian csc_matrix in same order as voxels
        in the region mask
    '''
    from friday_harbor.mask import Mask
    import numpy as np
    import warnings
    import scipy.sparse as sp
    
    def possible_neighbors(vox):
        '''
        Parameters
        ==========
          vox: 1x3 numpy array
        
        Returns
        =======
          neighbors: 6x3 numpy array, size 6 neighborhood voxel coordinates
        '''
        neighbors=np.tile(vox,(6,1))
        neighbors+=[[1,0,0],
                    [0,1,0],
                    [0,0,1],
                    [-1,0,0],
                    [0,-1,0],
                    [0,0,-1]]
        return neighbors
    
    voxels=np.array(mask.mask).T
    num_vox=len(mask)
    # num_vox=voxels.shape[0]
    vox_lookup={tuple(vox): idx for idx,vox in enumerate(voxels)}
    L=sp.lil_matrix((num_vox,num_vox))
    for idx,vox in enumerate(voxels):
        candidates=possible_neighbors(vox)
        deg=0
        for nei in candidates:
            try:
                idx_nei=vox_lookup[tuple(nei)]
                deg+=1
                L[idx,idx_nei]=1
            except KeyError:
                pass
        L[idx,idx]=-deg
    return L.tocsc()


def generate_voxel_matrices(data_dir,
                            source_id_list, target_id_list, 
                            min_voxels_per_injection=50,
                            source_coverage=0.8,
                            LIMS_id_list=None, source_shell=False,
                            laplacian=False, verbose=False):
    '''
    Generates the source and target expression matrices for a set of
    injections, which can then be used to fit the linear model, etc.
    Differs from 'generate_region_matrices' in that they are voxel-resolution,
    i.e. signals are not integrated across regions.

    Parameters
    ==========
      data_dir: directory containing hdf5 files
      source_id_list: source structure ids to consider
      target_id_list: target structure ids to consider
      min_voxels_per_injection, default=50
      source_coverage, default=0.8: fraction of injection density that should
        be contained in union of source regions
      LIMS_id_list: list of experiments to include
      source_shell, default=False: whether to use mask which draws a shell
        around source regions to account for extent of dendrites
      laplacian, default=False: return laplacian matrices?
      verbose, default=False: print progress
        
    Returns
    =======
      experiment_dict, with fields 'experiment_source_matrix',
        'experiment_target_matrix_ipsi', 'experiment_target_matrix_contra',
        'col_label_list_source', 'col_label_list_target', 'row_label_list',
        'source_laplacian', 'target_laplacian' (if laplacian==True)
    '''
    from friday_harbor.structure import Ontology
    from friday_harbor.mask import Mask
    from friday_harbor.experiment import ExperimentManager
    import numpy as np
    import scipy.sparse as sp
    import warnings
    import pdb
    #pdb.set_trace()
    from IPython import embed


    if verbose:
        print "Creating ExperimentManager and Ontology objects"
    EM=ExperimentManager(data_dir=data_dir)
    ontology=Ontology(data_dir=data_dir)

    if verbose:
        print "Creating experiment list"
    if LIMS_id_list == None:
        ex_list=EM.all()
        LIMS_id_list=[e.id for e in ex_list]
    else:
        ex_list=[EM.experiment_by_id(LIMS_id) for LIMS_id in LIMS_id_list]

    # Determine which experiments should be included:
    LIMS_id_list_new=[]
    ex_list_new=[]
    for ii,e in enumerate(ex_list):
        # Is the experiment target in one of the source region?
        # Note: does not check for leakage into other regions
        if e.structure_id in source_id_list:
            LIMS_id_list_new.append(LIMS_id_list[ii])
            ex_list_new.append(e)
    LIMS_id_list=LIMS_id_list_new
    ex_list=ex_list_new
    del LIMS_id_list_new
    del ex_list_new
    
    # Get the injection masks
    if verbose:
        print "Getting injection masks"
    PD_dict={e.id: e.density() for e in ex_list}
    injection_mask_dict={e.id: e.injection_mask() for e in ex_list}
    if source_shell:
        injection_mask_dict_shell={e.id: e.injection_mask(shell=True)
                                   for e in ex_list}
    else:
        injection_mask_dict_shell={}

    # Get the region masks
    if verbose:
        print "Getting region masks"
    region_mask_dict={}
    region_mask_ipsi_dict={}
    region_mask_contra_dict={}
    region_nvox={}
    region_ipsi_nvox={}
    region_contra_nvox={}
    nsource=0 # total voxels in sources
    nsource_ipsi=0
    ntarget_ipsi=0 # total voxels in ipsi targets
    ntarget_contra=0 # total voxels in contra targets
    source_indices={}
    source_ipsi_indices={}
    target_ipsi_indices={}
    target_contra_indices={}
    for struct_id in source_id_list:
        region_mask_dict[struct_id]=ontology.get_mask_from_id_nonzero(struct_id)
        region_mask_ipsi_dict[struct_id]=ontology.get_mask_from_id_right_hemisphere_nonzero(struct_id)
        region_mask_contra_dict[struct_id]=ontology.get_mask_from_id_left_hemisphere_nonzero(struct_id)
        region_nvox[struct_id]=len(region_mask_dict[struct_id])
        region_ipsi_nvox[struct_id]=len(region_mask_ipsi_dict[struct_id])
        region_contra_nvox[struct_id]=len(region_mask_contra_dict[struct_id])
        source_indices[struct_id]=np.arange(nsource,nsource+region_nvox[struct_id])
        source_ipsi_indices[struct_id]=np.arange(nsource_ipsi,nsource_ipsi+region_ipsi_nvox[struct_id])
        nsource+=region_nvox[struct_id]
        nsource_ipsi+=region_ipsi_nvox[struct_id]
    for struct_id in target_id_list:
        region_mask_dict[struct_id]=ontology.get_mask_from_id_nonzero(struct_id)
        region_mask_ipsi_dict[struct_id]=ontology.get_mask_from_id_right_hemisphere_nonzero(struct_id)
        region_mask_contra_dict[struct_id]=ontology.get_mask_from_id_left_hemisphere_nonzero(struct_id)
        region_nvox[struct_id]=len(region_mask_dict[struct_id])
        region_ipsi_nvox[struct_id]=len(region_mask_ipsi_dict[struct_id])
        region_contra_nvox[struct_id]=len(region_mask_contra_dict[struct_id])
        target_ipsi_indices[struct_id]=np.arange(ntarget_ipsi,ntarget_ipsi+region_ipsi_nvox[struct_id])
        target_contra_indices[struct_id]=np.arange(ntarget_contra,ntarget_contra+region_contra_nvox[struct_id])
        ntarget_ipsi+=region_ipsi_nvox[struct_id]
        ntarget_contra+=region_contra_nvox[struct_id]


    def get_integrated_PD(curr_LIMS_id, intersection_mask):
        def safe_sum(values):
            sum=0.0
            for val in values:
                if val == -1:
                    val=0.0
                elif val == -2:
                    warnings.warn(('projection density error -2, ',
                                   'missing tile in LIMS experiment %d')
                                  % curr_LIMS_id)
                    val=0.0
                elif val == -3:
                    warnings.warn(('projection density error -3, ',
                                   'no data in LIMS experiment %d')
                                  % curr_LIMS_id)
                    val=0.0
                sum+=val
            return sum
        if len(intersection_mask) > 0:
            curr_sum=safe_sum(PD_dict[curr_LIMS_id][intersection_mask.mask])
        else:
            curr_sum=0.0
        return curr_sum

    def get_PD(curr_LIMS_id, relevant_mask, region_mask):
        nvox=len(region_mask)
        if len(relevant_mask)>0:
            raw_pd=PD_dict[curr_LIMS_id][region_mask.mask]
            irrelevant_indices=np.ones((nvox,))
            list_relevant=zip(*relevant_mask.mask)
            list_region=zip(*region_mask.mask)
            for ii,el in enumerate(list_region):
                if el in list_relevant:
                    irrelevant_indices[ii]=0
            raw_pd[irrelevant_indices==1]=0.0
            errmask=raw_pd==-1
            if np.count_nonzero(errmask) > 0:
                raw_pd[errmask]=0.0
            errmask=raw_pd==-2
            if np.count_nonzero(errmask) > 0: 
                warnings.warn("projection density error -2, missing tile in LIMS experiment %d" \
                              % curr_LIMS_id)
                raw_pd[errmask]=0.0
            errmask=raw_pd==-3
            if np.count_nonzero(errmask) > 0: 
                warnings.warn("projection density error -3, no data in LIMS experiment %d" \
                              % curr_LIMS_id)
                raw_pd[errmask]=0.0
        else:
            raw_pd=np.zeros((nvox,))
        return raw_pd

    # Check for injection mask leaking into other region,
    # restrict to experiments w/o much leakage
    union_of_source_masks=Mask.union(*[region_mask_dict[id] for id in source_id_list])
    LIMS_id_list_new=[]
    for LIMS_id in LIMS_id_list:
        inj_mask=injection_mask_dict[LIMS_id]
        total_pd=get_integrated_PD(LIMS_id,inj_mask)
        total_source_pd=get_integrated_PD(LIMS_id,Mask.intersection(inj_mask,union_of_source_masks))
        source_frac=total_source_pd/total_pd
        if source_frac < source_coverage:
            del PD_dict[LIMS_id]
            del injection_mask_dict[LIMS_id]
            if source_shell:
                del injection_mask_dict_shell[LIMS_id]
        else:
            LIMS_id_list_new.append(LIMS_id)
    LIMS_id_list=LIMS_id_list_new
    del LIMS_id_list_new
    
    # Initialize matrices:
    structures_above_threshold_ind_list=[]
    experiment_source_matrix_pre=np.zeros((len(LIMS_id_list),nsource_ipsi))
    col_label_list_source=np.zeros((nsource_ipsi,1))
    voxel_coords_source=np.zeros((nsource_ipsi,3))
    
    # Source
    if verbose:
        print "Getting source densities"
    for jj, struct_id in enumerate(source_id_list):
        # Get the region mask:
        curr_region_mask=region_mask_ipsi_dict[struct_id]
        ipsi_injection_volume_list=[]
        for ii, curr_LIMS_id in enumerate(LIMS_id_list):
            # Get the injection mask:
            curr_experiment_mask=injection_mask_dict[curr_LIMS_id]
            # Compute density, source:
            intersection_mask=Mask.intersection(curr_experiment_mask, 
                                                curr_region_mask)
            if len(intersection_mask)>0:
                pd_at_intersect=get_PD(curr_LIMS_id,intersection_mask,curr_region_mask)
                indices=source_ipsi_indices[struct_id]
                experiment_source_matrix_pre[ii,indices]=pd_at_intersect
                ipsi_injection_volume_list.append(len(intersection_mask))
                col_label_list_source[indices]=struct_id
                voxel_coords_source[indices,]=np.array(curr_region_mask.mask).T
        
        # Determine if current structure should be included in source list:
        ipsi_injection_volume_array=np.array(ipsi_injection_volume_list)
        num_exp_above_thresh=len(np.nonzero(ipsi_injection_volume_array 
                                            >= min_voxels_per_injection)[0])
        if num_exp_above_thresh > 0:
            structures_above_threshold_ind_list.append(jj)
            if verbose:
                print("structure %s above threshold") % struct_id

    # if len(structures_above_threshold_ind_list) < len(source_id_list):
    #     raise Exception('length of structures_above_threshold_ind_list < source_id_list')
    # # restrict matrices to the good experiments & structures
    # above_threshold_indices=
    # experiment_source_matrix=experiment_source_matrix_pre[:,structures_above_threshold_ind_list]
    experiment_source_matrix=experiment_source_matrix_pre
    row_label_list=np.array(LIMS_id_list)
     
    # Target:
    if verbose:
        print "Getting target densities"
    experiment_target_matrix_ipsi=np.zeros((len(LIMS_id_list), 
                                            ntarget_ipsi))
    experiment_target_matrix_contra=np.zeros((len(LIMS_id_list), 
                                              ntarget_contra))
    col_label_list_target_ipsi=np.zeros((ntarget_ipsi,1))
    col_label_list_target_contra=np.zeros((ntarget_contra,1))
    voxel_coords_target_ipsi=np.zeros((ntarget_ipsi,3))
    voxel_coords_target_contra=np.zeros((ntarget_contra,3))
    for jj, struct_id in enumerate(target_id_list):
        # Get the region mask:
        curr_region_mask_ipsi=region_mask_ipsi_dict[struct_id]
        curr_region_mask_contra=region_mask_contra_dict[struct_id]
        for ii, curr_LIMS_id in enumerate(row_label_list):
            # Get the injection mask:
            if source_shell == True:
                curr_experiment_mask=injection_mask_dict_shell[curr_LIMS_id]
            else:
                curr_experiment_mask=injection_mask_dict[curr_LIMS_id]
            # Compute integrated density, target, ipsi:
            difference_mask=curr_region_mask_ipsi.difference(curr_experiment_mask)
            indices_ipsi=target_ipsi_indices[struct_id]
            pd_at_diff=get_PD(curr_LIMS_id,difference_mask,curr_region_mask_ipsi)
            experiment_target_matrix_ipsi[ii, indices_ipsi]=pd_at_diff
            col_label_list_target_ipsi[indices_ipsi]=struct_id
            voxel_coords_target_ipsi[indices_ipsi,]=np.array(curr_region_mask_ipsi.mask).T
            # Compute integrated density, target, contra:    
            difference_mask=curr_region_mask_contra.difference(curr_experiment_mask)
            indices_contra=target_contra_indices[struct_id]
            pd_at_diff=get_PD(curr_LIMS_id,difference_mask,curr_region_mask_contra)
            experiment_target_matrix_contra[ii, indices_contra]=pd_at_diff
            col_label_list_target_contra[indices_contra]=struct_id
            voxel_coords_target_contra[indices_contra,]=np.array(curr_region_mask_contra.mask).T

    if verbose:
        print "Getting laplacians"
    # Laplacians
    if laplacian:
        Lx=sp.block_diag(tuple([region_laplacian(region_mask_ipsi_dict[region])
                          for region in source_id_list]))
        Ly_ipsi=sp.block_diag(tuple([region_laplacian(region_mask_ipsi_dict[region])
                               for region in target_id_list]))
        Ly_contra=sp.block_diag(tuple([region_laplacian(region_mask_contra_dict[region])
                                 for region in target_id_list]))
    Lx=sp.csc_matrix(Lx)
    Ly_ipsi=sp.csc_matrix(Ly_ipsi)
    Ly_contra=sp.csc_matrix(Ly_contra)

    if verbose:
        print "Done."
    # Include only structures with sufficient injection information, and 
    # experiments with one nonzero entry in row:
    experiment_dict={}
    experiment_dict['experiment_source_matrix']=experiment_source_matrix
    experiment_dict['experiment_target_matrix_ipsi']=experiment_target_matrix_ipsi
    experiment_dict['experiment_target_matrix_contra']=experiment_target_matrix_contra
    experiment_dict['col_label_list_source']=col_label_list_source 
    experiment_dict['col_label_list_target_ipsi']=col_label_list_target_ipsi
    experiment_dict['col_label_list_target_contra']=col_label_list_target_contra
    experiment_dict['row_label_list']=row_label_list
    experiment_dict['voxel_coords_source']=voxel_coords_source
    experiment_dict['voxel_coords_target_ipsi']=voxel_coords_target_ipsi
    experiment_dict['voxel_coords_target_contra']=voxel_coords_target_contra
    if laplacian:
        experiment_dict['Lx']=Lx
        experiment_dict['Ly_ipsi']=Ly_ipsi
        experiment_dict['Ly_contra']=Ly_contra
    
    return experiment_dict
