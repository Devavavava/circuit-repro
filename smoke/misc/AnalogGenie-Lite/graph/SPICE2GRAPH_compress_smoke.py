import pandas as pd

def read_netlist(filename):
    with open(filename, 'r') as file:
        lines = file.readlines()
    netlist = []
    for line in lines:
        parts = line.strip().replace('(', '').replace(')', '').split()
        netlist.append(parts)
    return netlist

def read_ports(filename):
    with open(filename, 'r') as file:
        ports = file.readline().strip().split()
    return ports

def build_connection_matrix(netlist, ports):
    # Initialize node list with ports
    nodes = ports[:]
    
    # Counters for each component type
    counters = {
        'pmos4': 1,
        'nmos4': 1,
        'npn': 1,
        'pnp': 1,
        'resistor': 1,
        'capacitor': 1,
        'inductor': 1,
        'diode': 1,
        'XOR': 1,
        'PFD': 1,
        'INVERTER': 1,
        'TRANSMISSION_GATE': 1
    }
    
    # Define node types based on the component type
    node_types = {
        'pmos4': lambda i: [f'PM{i}', f'PM{i}_D', f'PM{i}_G', f'PM{i}_S', f'PM{i}_B'],
        'nmos4': lambda i: [f'NM{i}', f'NM{i}_D', f'NM{i}_G', f'NM{i}_S', f'NM{i}_B'],
        'npn': lambda i: [f'NPN{i}', f'NPN{i}_C', f'NPN{i}_B', f'NPN{i}_E'],
        'pnp': lambda i: [f'PNP{i}', f'PNP{i}_C', f'PNP{i}_B', f'PNP{i}_E'],
        'resistor': lambda i: [f'R{i}', f'R{i}_P', f'R{i}_N'],
        'capacitor': lambda i: [f'C{i}', f'C{i}_P', f'C{i}_N'],
        'inductor': lambda i: [f'L{i}', f'L{i}_P', f'L{i}_N'],
        'diode': lambda i: [f'DIO{i}', f'DIO{i}_P', f'DIO{i}_N'],
        'XOR': lambda i: [f'XOR{i}', f'XOR{i}_A', f'XOR{i}_B', f'XOR{i}_VDD', f'XOR{i}_VSS', f'XOR{i}_Y'],
        'PFD': lambda i: [f'PFD{i}', f'PFD{i}_A', f'PFD{i}_B', f'PFD{i}_QA', f'PFD{i}_QB', f'PFD{i}_VDD', f'PFD{i}_VSS'],
        'INVERTER': lambda i: [f'INVERTER{i}', f'INVERTER{i}_A', f'INVERTER{i}_Q', f'INVERTER{i}_VDD', f'INVERTER{i}_VSS'],
        'TRANSMISSION_GATE': lambda i: [f'TRANSMISSION_GATE{i}', f'TRANSMISSION_GATE{i}_A', f'TRANSMISSION_GATE{i}_B', f'TRANSMISSION_GATE{i}_C', f'TRANSMISSION_GATE{i}_VDD', f'TRANSMISSION_GATE{i}_VSS'],
    }
    node_types_simple = {
        'pmos4': lambda i: [f'PM{i}_D', f'PM{i}_G', f'PM{i}_S', f'PM{i}_B'],
        'nmos4': lambda i: [f'NM{i}_D', f'NM{i}_G', f'NM{i}_S', f'NM{i}_B'],
        'npn': lambda i: [f'NPN{i}_C', f'NPN{i}_B', f'NPN{i}_E'],
        'pnp': lambda i: [f'PNP{i}_C', f'PNP{i}_B', f'PNP{i}_E'],
        'resistor': lambda i: [f'R{i}_P', f'R{i}_N'],
        'capacitor': lambda i: [f'C{i}_P', f'C{i}_N'],
        'inductor': lambda i: [f'L{i}_P', f'L{i}_N'],
        'diode': lambda i: [f'DIO{i}_P', f'DIO{i}_N'],
        'XOR': lambda i: [f'XOR{i}_A', f'XOR{i}_B', f'XOR{i}_VDD', f'XOR{i}_VSS', f'XOR{i}_Y'],
        'PFD': lambda i: [f'PFD{i}_A', f'PFD{i}_B', f'PFD{i}_QA', f'PFD{i}_QB', f'PFD{i}_VDD', f'PFD{i}_VSS'],
        'INVERTER': lambda i: [f'INVERTER{i}_A', f'INVERTER{i}_Q', f'INVERTER{i}_VDD', f'INVERTER{i}_VSS'],
        'TRANSMISSION_GATE': lambda i: [f'TRANSMISSION_GATE{i}_A', f'TRANSMISSION_GATE{i}_B', f'TRANSMISSION_GATE{i}_C', f'TRANSMISSION_GATE{i}_VDD', f'TRANSMISSION_GATE{i}_VSS'],
    }
    
    # Initialize component lists
    nmos_list = []
    pmos_list = []
    npn_list = []
    pnp_list = []
    resistor_list = []
    capacitor_list = []
    inductor_list = []
    diode_list = []
    XOR_list = []
    PFD_list = []
    INVERTER_list = []
    TRANSMISSION_GATE_list = []
    net_connections = []
    
    # Iterate through the netlist to add component nodes
    for component in netlist:
        # print(component)
        component_type = component[-1]
        if component_type in node_types:
            nodes_to_add = node_types[component_type](counters[component_type])
            nodes_trully_add = node_types_simple[component_type](counters[component_type])
            # print(nodes_to_add)
            # print(nodes_trully_add)
            # print(nodes)
            nodes.extend(nodes_trully_add)
            if component_type == 'nmos4':
                nmos_list.append((nodes_to_add[0], component))
            elif component_type == 'pmos4':
                pmos_list.append((nodes_to_add[0], component))
            elif component_type == 'npn':
                npn_list.append((nodes_to_add[0], component))
            elif component_type == 'pnp':
                pnp_list.append((nodes_to_add[0], component))
            elif component_type == 'resistor':
                resistor_list.append((nodes_to_add[0], component))
            elif component_type == 'capacitor':
                capacitor_list.append((nodes_to_add[0], component))
            elif component_type == 'inductor':
                inductor_list.append((nodes_to_add[0], component))
            elif component_type == 'diode':
                diode_list.append((nodes_to_add[0], component))
            elif component_type == 'XOR':
                XOR_list.append((nodes_to_add[0], component))
            elif component_type == 'PFD':
                PFD_list.append((nodes_to_add[0], component))
            elif component_type == 'INVERTER':
                INVERTER_list.append((nodes_to_add[0], component))
            elif component_type == 'TRANSMISSION_GATE':
                TRANSMISSION_GATE_list.append((nodes_to_add[0], component))
            counters[component_type] += 1
    
    # print(nodes)
    # Create an empty connection matrix
    matrix = pd.DataFrame(0, index=nodes, columns=nodes)

    # print(nmos_list)
    
    # Fill the matrix based on NM# and PM# connections
    for nm, _ in nmos_list:
        matrix.iloc[nodes.index(f'{nm}_G'), nodes.index(f'{nm}_D')] = 1
        matrix.iloc[nodes.index(f'{nm}_D'), nodes.index(f'{nm}_B')] = 1
        matrix.iloc[nodes.index(f'{nm}_B'), nodes.index(f'{nm}_S')] = 1
        matrix.iloc[nodes.index(f'{nm}_S'), nodes.index(f'{nm}_G')] = 1

        matrix.iloc[nodes.index(f'{nm}_D'), nodes.index(f'{nm}_G')] = 1
        matrix.iloc[nodes.index(f'{nm}_B'), nodes.index(f'{nm}_D')] = 1
        matrix.iloc[nodes.index(f'{nm}_S'), nodes.index(f'{nm}_B')] = 1
        matrix.iloc[nodes.index(f'{nm}_G'), nodes.index(f'{nm}_S')] = 1


    for pm, _ in pmos_list:
        matrix.iloc[nodes.index(f'{pm}_G'), nodes.index(f'{pm}_D')] = 1
        matrix.iloc[nodes.index(f'{pm}_D'), nodes.index(f'{pm}_B')] = 1
        matrix.iloc[nodes.index(f'{pm}_B'), nodes.index(f'{pm}_S')] = 1
        matrix.iloc[nodes.index(f'{pm}_S'), nodes.index(f'{pm}_G')] = 1

        matrix.iloc[nodes.index(f'{pm}_D'), nodes.index(f'{pm}_G')] = 1
        matrix.iloc[nodes.index(f'{pm}_B'), nodes.index(f'{pm}_D')] = 1
        matrix.iloc[nodes.index(f'{pm}_S'), nodes.index(f'{pm}_B')] = 1
        matrix.iloc[nodes.index(f'{pm}_G'), nodes.index(f'{pm}_S')] = 1

    for npn, _ in npn_list:
        matrix.iloc[nodes.index(f'{npn}_B'), nodes.index(f'{npn}_C')] = 1
        matrix.iloc[nodes.index(f'{npn}_C'), nodes.index(f'{npn}_E')] = 1
        matrix.iloc[nodes.index(f'{npn}_E'), nodes.index(f'{npn}_B')] = 1

        matrix.iloc[nodes.index(f'{npn}_C'), nodes.index(f'{npn}_B')] = 1
        matrix.iloc[nodes.index(f'{npn}_E'), nodes.index(f'{npn}_C')] = 1
        matrix.iloc[nodes.index(f'{npn}_B'), nodes.index(f'{npn}_E')] = 1

    for pnp, _ in pnp_list:
        matrix.iloc[nodes.index(f'{pnp}_B'), nodes.index(f'{pnp}_C')] = 1
        matrix.iloc[nodes.index(f'{pnp}_C'), nodes.index(f'{pnp}_E')] = 1
        matrix.iloc[nodes.index(f'{pnp}_E'), nodes.index(f'{pnp}_B')] = 1

        matrix.iloc[nodes.index(f'{pnp}_C'), nodes.index(f'{pnp}_B')] = 1
        matrix.iloc[nodes.index(f'{pnp}_E'), nodes.index(f'{pnp}_C')] = 1
        matrix.iloc[nodes.index(f'{pnp}_B'), nodes.index(f'{pnp}_E')] = 1

    for r, _ in resistor_list:
        matrix.iloc[nodes.index(f'{r}_P'), nodes.index(f'{r}_N')] = 1
        matrix.iloc[nodes.index(f'{r}_N'), nodes.index(f'{r}_P')] = 1

    for c, _ in capacitor_list:
        matrix.iloc[nodes.index(f'{c}_P'), nodes.index(f'{c}_N')] = 1
        matrix.iloc[nodes.index(f'{c}_N'), nodes.index(f'{c}_P')] = 1

    for l, _ in inductor_list:
        matrix.iloc[nodes.index(f'{l}_P'), nodes.index(f'{l}_N')] = 1
        matrix.iloc[nodes.index(f'{l}_N'), nodes.index(f'{l}_P')] = 1

    for dio, _ in diode_list:
        matrix.iloc[nodes.index(f'{dio}_P'), nodes.index(f'{dio}_N')] = 1
        matrix.iloc[nodes.index(f'{dio}_N'), nodes.index(f'{dio}_P')] = 1

    for xor, _ in XOR_list:
        matrix.iloc[nodes.index(f'{xor}_A'), nodes.index(f'{xor}_B')] = 1
        matrix.iloc[nodes.index(f'{xor}_B'), nodes.index(f'{xor}_VDD')] = 1
        matrix.iloc[nodes.index(f'{xor}_VDD'), nodes.index(f'{xor}_Y')] = 1
        matrix.iloc[nodes.index(f'{xor}_Y'), nodes.index(f'{xor}_VSS')] = 1
        matrix.iloc[nodes.index(f'{xor}_VSS'), nodes.index(f'{xor}_A')] = 1

        matrix.iloc[nodes.index(f'{xor}_B'), nodes.index(f'{xor}_A')] = 1
        matrix.iloc[nodes.index(f'{xor}_VDD'), nodes.index(f'{xor}_B')] = 1
        matrix.iloc[nodes.index(f'{xor}_Y'), nodes.index(f'{xor}_VDD')] = 1
        matrix.iloc[nodes.index(f'{xor}_VSS'), nodes.index(f'{xor}_Y')] = 1
        matrix.iloc[nodes.index(f'{xor}_A'), nodes.index(f'{xor}_VSS')] = 1

    for pfd, _ in PFD_list:
        matrix.iloc[nodes.index(f'{pfd}_A'), nodes.index(f'{pfd}_B')] = 1
        matrix.iloc[nodes.index(f'{pfd}_B'), nodes.index(f'{pfd}_VDD')] = 1
        matrix.iloc[nodes.index(f'{pfd}_VDD'), nodes.index(f'{pfd}_QA')] = 1
        matrix.iloc[nodes.index(f'{pfd}_QA'), nodes.index(f'{pfd}_QB')] = 1
        matrix.iloc[nodes.index(f'{pfd}_QB'), nodes.index(f'{pfd}_VSS')] = 1
        matrix.iloc[nodes.index(f'{pfd}_VSS'), nodes.index(f'{pfd}_A')] = 1

        matrix.iloc[nodes.index(f'{pfd}_B'), nodes.index(f'{pfd}_A')] = 1
        matrix.iloc[nodes.index(f'{pfd}_VDD'), nodes.index(f'{pfd}_B')] = 1
        matrix.iloc[nodes.index(f'{pfd}_QA'), nodes.index(f'{pfd}_VDD')] = 1
        matrix.iloc[nodes.index(f'{pfd}_QB'), nodes.index(f'{pfd}_QA')] = 1
        matrix.iloc[nodes.index(f'{pfd}_VSS'), nodes.index(f'{pfd}_QB')] = 1
        matrix.iloc[nodes.index(f'{pfd}_A'), nodes.index(f'{pfd}_VSS')] = 1

    for inv, _ in INVERTER_list:
        matrix.iloc[nodes.index(f'{inv}_A'), nodes.index(f'{inv}_VDD')] = 1
        matrix.iloc[nodes.index(f'{inv}_VDD'), nodes.index(f'{inv}_Q')] = 1
        matrix.iloc[nodes.index(f'{inv}_Q'), nodes.index(f'{inv}_VSS')] = 1
        matrix.iloc[nodes.index(f'{inv}_VSS'), nodes.index(f'{inv}_A')] = 1

        matrix.iloc[nodes.index(f'{inv}_VDD'), nodes.index(f'{inv}_A')] = 1
        matrix.iloc[nodes.index(f'{inv}_Q'), nodes.index(f'{inv}_VDD')] = 1
        matrix.iloc[nodes.index(f'{inv}_VSS'), nodes.index(f'{inv}_Q')] = 1
        matrix.iloc[nodes.index(f'{inv}_A'), nodes.index(f'{inv}_VSS')] = 1

    for tg, _ in TRANSMISSION_GATE_list:
        matrix.iloc[nodes.index(f'{tg}_A'), nodes.index(f'{tg}_VDD')] = 1
        matrix.iloc[nodes.index(f'{tg}_VDD'), nodes.index(f'{tg}_C')] = 1
        matrix.iloc[nodes.index(f'{tg}_C'), nodes.index(f'{tg}_B')] = 1
        matrix.iloc[nodes.index(f'{tg}_B'), nodes.index(f'{tg}_VSS')] = 1
        matrix.iloc[nodes.index(f'{tg}_VSS'), nodes.index(f'{tg}_A')] = 1

        matrix.iloc[nodes.index(f'{tg}_VDD'), nodes.index(f'{tg}_A')] = 1
        matrix.iloc[nodes.index(f'{tg}_C'), nodes.index(f'{tg}_VDD')] = 1
        matrix.iloc[nodes.index(f'{tg}_B'), nodes.index(f'{tg}_C')] = 1
        matrix.iloc[nodes.index(f'{tg}_VSS'), nodes.index(f'{tg}_B')] = 1
        matrix.iloc[nodes.index(f'{tg}_A'), nodes.index(f'{tg}_VSS')] = 1


    # Fill the matrix based on the connections from the netlist
    new_counters = {
        'pmos4': 1,
        'nmos4': 1,
        'npn': 1,
        'pnp': 1,
        'resistor': 1,
        'capacitor': 1,
        'inductor': 1,
        'diode': 1,
        'XOR': 1,
        'PFD': 1,
        'INVERTER': 1,
        'TRANSMISSION_GATE': 1
    }
    for component in netlist:
        element = component[1:-1]
        # print(element)
        component_type = component[-1]
        # print(component_type)
        # print(new_counters)
        index = new_counters[component_type]
        new_counters[component_type] += 1
        # print(index)
        if component_type == 'nmos4':
            connections = [f'NM{index}_D', f'NM{index}_G', f'NM{index}_S', f'NM{index}_B']
        elif component_type == 'pmos4':
            connections = [f'PM{index}_D', f'PM{index}_G', f'PM{index}_S', f'PM{index}_B']
        elif component_type == 'npn':
            connections = [f'NPN{index}_C', f'NPN{index}_B', f'NPN{index}_E']
        elif component_type == 'pnp':
            connections = [f'PNP{index}_C', f'PNP{index}_B', f'PNP{index}_E']
        elif component_type == 'resistor':
            connections = [f'R{index}_P', f'R{index}_N']
        elif component_type == 'capacitor':
            connections = [f'C{index}_P', f'C{index}_N']
        elif component_type == 'inductor':
            connections = [f'L{index}_P', f'L{index}_N']
        elif component_type == 'diode':
            connections = [f'DIO{index}_P', f'DIO{index}_N']
        elif component_type == 'XOR':
            connections = [f'XOR{index}_A', f'XOR{index}_B', f'XOR{index}_VDD', f'XOR{index}_VSS', f'XOR{index}_Y']
        elif component_type == 'PFD':
            connections = [f'PFD{index}_A', f'PFD{index}_B', f'PFD{index}_QA', f'PFD{index}_QB', f'PFD{index}_VDD', f'PFD{index}_VSS']
        elif component_type == 'INVERTER':
            connections = [f'INVERTER{index}_A', f'INVERTER{index}_Q', f'INVERTER{index}_VDD', f'INVERTER{index}_VSS']
        elif component_type == 'TRANSMISSION_GATE':
            connections = [f'TRANSMISSION_GATE{index}_A', f'TRANSMISSION_GATE{index}_B', f'TRANSMISSION_GATE{index}_C', f'TRANSMISSION_GATE{index}_VDD', f'TRANSMISSION_GATE{index}_VSS']
        
        for conn, el in zip(connections, element):
            if el in nodes:
                matrix.at[conn, el] = 1
                matrix.at[el, conn] = 1
            else:
                net_connections.append((conn, el))

    # Create a dictionary to store net to nodes mapping
    net_dict = {}
    for conn, net in net_connections:
        if net not in net_dict:
            net_dict[net] = []
        net_dict[net].append(conn)
    # print(net_dict)

    # Fill the matrix with indirect connections based on net sharing
    for net, conn_list in net_dict.items():
        for i in range(len(conn_list)):
            for j in range(i + 1, len(conn_list)):
                matrix.at[conn_list[i], conn_list[j]] = 1
                matrix.at[conn_list[j], conn_list[i]] = 1
    
    return matrix, net_connections

# start = 1
# end = 801
# for i in range (start, end):
#     print(i)
#     number = str(i)
#     # Define file names
#     netlist_file = number + '/' + number + '.cir'
#     port_file =  number + '/' + 'Port' + number + '.txt' 

#     # Read netlist and ports
#     netlist = read_netlist(netlist_file)
#     # print(netlist)
#     ports = read_ports(port_file)
#     # print(netlist)

#     # Build the connection matrix
#     connection_matrix, net_connections = build_connection_matrix(netlist, ports)

#     # Display the connection matrix
#     # print(connection_matrix)

#     # Print net connections
#     # print("Net Connections:")
#     # for conn in net_connections:
#     #     print(f"{conn[0]} connect to {conn[1]} undirectly")


#     # If you want to save the matrix to a file, uncomment the following line
#     csv_name =  number + '/Graph' + number + '_compress.csv'
#     connection_matrix.to_csv(csv_name)


base_dirs = {
    "C:/Users/Devavrat/circuit-repro/AnalogGenie/repo/Dataset": 25,
}

for base_dir, end in base_dirs.items():
    for i in range(1, end):
        print(f"Processing directory: {base_dir}, file: {i}")
        number = str(i)

        # Define file names
        netlist_file = f"{base_dir}/{number}/{number}.cir"
        port_file = f"{base_dir}/{number}/Port{number}.txt"

        try:
            # Read netlist and ports
            netlist = read_netlist(netlist_file)
            ports = read_ports(port_file)

            # Build the connection matrix
            connection_matrix, net_connections = build_connection_matrix(netlist, ports)

            # If you want to save the matrix to a file
            csv_name = f"{base_dir}/{number}/Graph{number}_compress.csv"
            connection_matrix.to_csv(csv_name)
        except Exception as e:
            print(f"Error processing {netlist_file} or {port_file}: {e}")