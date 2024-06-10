
import sys, os, getopt, time
from src.tracET.core.vtk_uts import *
from src.tracET.core import lio
from src.tracET.representation.graphs import *
#import nrrd
import pandas as pd

def main(argv):
    start = time.time()

    #Input parsing
    main_dir = None
    in_tomo, out_dir = None, None
    r, s = None, None
    t,b=None,None
    try:
        opts, args = getopt.getopt(argv, "hm:i:r:s:t:b:o:",["help","main","itomo","rad","subsam","type","branch","odir"])
    except getopt.GetoptError:
        print('python trace_graph.py -i <in_tomo> -r <radius> -s <subsampling> -o <out_dir>')
        sys.exit()
    for opt, arg in opts:
        if opt in ("-h","--help"):
            print('python trace_graph.py - m <main_dir> -i <in_tomo> -r <radius> -s <subsampling> -o <out_dir>')
            print('\t-m (--main) main directory ')
            print('\t-i (--itomo) <in_tomo> input tomogram (point cloud)')
            print('\t-r (--rad) <radius> radius to connect points in the graph')
            print('\t-s (--subsam) <subsampling> radius of subsampling (optional, default no subsampling)')
            print('\t-t (--type) <type of filament> "l" (linear) or "n" (net) (optional, default linear)')
            print('\t-b (--branch) <branch grade> times we repeat the branch removal for branches with more than one edge. (optional, default 1. Only for linear)')
            print('\t-o (--odir) <out_dir> putput directory')
        elif opt in ("-m","--main"):
            main_dir = arg
        elif opt in ("-i","--itomo"):
            in_tomo=arg
            if not(os.path.splitext(in_tomo)[1] in ('.mrc', '.nhdr', '.nrrd')):
                print('The input file must have a .mrc, .nhdr or nrrd extension!')
                sys.exit()
        elif opt in ("-r","--rad"):
            r=arg
        elif opt in ("-s","--subsam"):
            s=arg
        elif opt in ("-t","--type"):
            t=arg
        elif opt in ("-b","--branch"):
            b=arg
        elif opt in ("-o","--odir"):
            out_dir=arg

    if main_dir is not None:
        print('\t-Main directory:', main_dir)
    else:
        print('python trace_graph.py - m <main_dir> -i <in_tomo> -r <radius> -s <subsampling> -o <out_dir>')
        print('Almost a main directory -m must be provided')
    if in_tomo is not None:
        print('\t-Loading input tomogram:', in_tomo)
        if os.path.splitext(in_tomo)[1] == '.mrc':
            T = lio.load_mrc(main_dir + in_tomo)
        else:
            T = nrrd.read(main_dir+in_tomo)[0]
    else:
        print('python trace_graph.py -i <in_tomo> -r <radius> -s <subsampling> -o <out_dir>')
        print('Almost an input tomogram -i must be provided')
        sys.exit()
    if r is not None:
        print('Radius = ',str(r))
    else:
        print('python trace_graph.py -i <in_tomo> -r <radius> -s <subsampling> -o <out_dir>')
        print('Almost an input radius -r must be provided')
        sys.exit()
    if s is not None:
        print ('Subsampling radius = ',str(s))
    else:
        s=0
        print('Default no subsampling')
    if t is not None:
        print('Type of filament = ',str(t))
    else:
        t='l'
        print('Default: linear filament')
    if b is not None:
        print('Branch grade = ',str(b))
    else:
        b=1
        print('Default: branches grade one')
    if out_dir is not None:
        print ('Save out vtp in: ',out_dir)
    else:
        print('python trace_graph.py -i <in_tomo> -r <radius> -s <subsampling> -o <out_dir>')
        print('Almost an output directory -o must be provided')
        sys.exit()


    print('Calculating the graph')
    [coords, graph_array] =make_skeleton_graph(T,float(r),float(s))
    #Targets_0, Sources_0 = (graph_array.nonzero())
    #unproceseed_points_poly = make_graph_polydata(coords, Sources_0, Targets_0)
    #save_vtp(unproceseed_points_poly, main_dir + os.path.splitext(in_tomo)[0] + '_unprocessed_skel_graph.vtp')
    print('Spliting in components')
    [graph_ar_comps,coords_comps]=split_into_components(graph_array,coords)
    print('Making graphs line like and save')
    tubule_list=np.zeros(len(coords))
    a=0
    #append_comps = vtk.vtkAppendPolyData()
    for i in range(len(graph_ar_comps)):
        print('Procesing tubule ',str(i))
        #Targets_comp, Sources_comp = (graph_ar_comps[i].nonzero())
        #comp_points_poly = make_graph_polydata(coords_comps[i], Sources_comp, Targets_comp)
        #save_vtp(comp_points_poly, main_dir +'comps/'+ os.path.splitext(in_tomo)[0] + '_comp_'+str(i)+'_skel_graph.vtp')
        print('Removing cycles')
        L_graph=spannig_tree_apply(graph_ar_comps[i])
        #Targets_nc, Sources_nc = (L_graph.nonzero())
        #nc_points_poly = make_graph_polydata(coords_comps[i], Sources_nc, Targets_nc)
        #save_vtp(nc_points_poly,main_dir + 'comps/' + os.path.splitext(in_tomo)[0] + '_comp_' + str(i) + 'nc_skel_graph.vtp')
       # L_graph=remove_cycles(L_graph)
        if t=='l':
            print('For a linear filament, we remove the shortest branches')
            L_coords = coords_comps[i]
            for number in range(int(b)):
                L_graph,L_coords=remove_branches(L_graph,L_coords)
                L_branches=np.ones((len(L_coords)))
                print(number)
        else:
            print('For a net, we leave the branches')
            L_graph,L_coords,L_branches=label_branches2(L_graph,coords_comps[i])
            #L_coords=coords_comps[i]

        ##curve processign
        ##graph_branch_coords_branch = split_into_components(L_graph,L_coords)



        print('Make polydata')
        Targets, Sources = (L_graph.nonzero())
        if i == 0:
            points_poly0 = make_graph_polydata(L_coords,Sources,Targets)
            add_label_to_poly(points_poly0,i,'component')
            add_labels_to_poly(points_poly0, L_branches, 'branches')
        elif i == 1:
            points_poly1 = make_graph_polydata(L_coords,Sources,Targets)
            add_label_to_poly(points_poly1, i, 'component')
            add_labels_to_poly(points_poly1, L_branches, 'branches')
            points_poly = merge_polys(points_poly0,points_poly1)
        else:
            points_polyi= make_graph_polydata(L_coords,Sources,Targets)
            add_label_to_poly(points_polyi, i, 'component')
            add_labels_to_poly(points_polyi, L_branches, 'branches')
            points_poly = merge_polys(points_poly,points_polyi)
        #append_comps.AddInputData(points_poly)
        #print('Saving')
        #save_vtp(points_poly, main_dir+ out_dir + os.path.splitext(in_tomo)[0]+ '_skel_graph_tubule_'+str(i)+'.vtp')
        #print(os.path.splitext(in_tomo)[0]+ '_skel_graph_tubule_'+str(i)+'.vtp'+' saved in '+main_dir+out_dir)
        tubule_list[a:a+len(coords_comps[i])]=i*np.ones(len(coords_comps[i]))
        a=a+len(coords_comps[i])
    out_mat=np.zeros((len(coords),4))
    out_mat[:,0]=tubule_list
    out_mat[:,1:4]=coords
    out_pd=pd.DataFrame(data=out_mat,columns=['Filament','X','Y','Z'])
    out_pd.to_csv(main_dir+os.path.splitext(in_tomo)[0]+ '_skel_graph.csv')
    #append_comps.Update()
    #complete_graph_poly = append_comps.GetOutput()
    #add_atributte_to_poly(complete_graph_poly,np.array(tubule_list).astype(np.float32),'component')
    #tubule_data=complete_graph_poly.GetPointData().GetArray('component')
    #tubule_values=[]
    #for i in range(tubule_data.GetNumberOfTuples()):
        #tubule_values.append(tubule_data.GetValue(i))
    save_vtp(points_poly, main_dir + os.path.splitext(in_tomo)[0] + '_skel_graph.vtp')
    end = time.time()
    print('The program lasted ', str(end - start), ' s in execute')
    print('Successfully terminated. (' + time.strftime("%c") + ')')

if __name__ == "__main__":
    main(sys.argv[1:])