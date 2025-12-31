import time
import timeout_decorator
from agent_baselines import Agent
import networkx as nx
import random

class StudentAgent(Agent):
    @timeout_decorator.timeout(1)
    def __init__(self, agent_name='Greedy Strategy'):
        super().__init__(agent_name)

    @timeout_decorator.timeout(1)
    def new_game(self, game, power_name):
        self.game = game
        self.power_name = power_name
        self.build_map_graphs()
        self._previous_scs = len(self.game.get_centers(self.power_name))

    @timeout_decorator.timeout(1) # This is only for updating the game engine and other states if any. Do not implement heavy stratergy here.
    def update_game(self, all_power_orders):
        # do not make changes to the following codes
        for power_name in all_power_orders.keys():
            self.game.set_orders(power_name, all_power_orders[power_name])
        self.game.process()
    
    def build_map_graphs(self):
        if not self.game:
            raise Exception('Game Not Initialised. Cannot Build Map Graphs.')

        self.map_graph_army = nx.Graph()
        self.map_graph_navy = nx.Graph()

        locations = list(self.game.map.loc_type.keys()) # locations with '/' are not real provinces

        for i in locations:
            if self.game.map.loc_type[i] in ['LAND', 'COAST']:
                self.map_graph_army.add_node(i.upper())
            if self.game.map.loc_type[i] in ['WATER', 'COAST']:
                self.map_graph_navy.add_node(i.upper())

        locations = [i.upper() for i in locations]

        for i in locations:
            for j in locations:
                if self.game.map.abuts('A', i, '-', j):
                    self.map_graph_army.add_edge(i, j)
                if self.game.map.abuts('F', i, '-', j):
                    self.map_graph_navy.add_edge(i, j)

    @timeout_decorator.timeout(1)
    def get_actions(self):
        possible_orders = self.game.get_all_possible_orders()
        orderable_locations = self.game.get_orderable_locations(self.power_name)

        if self.game.phase_type == 'M':
            ...
        elif self.game.phase_type == 'R':
            ...
        else:
            # Calculate the number of supply centres owned as well as current units maintained
            owned_scs_count = len(self.game.get_centers(self.power_name))
            units_count = len(self.game.get_units(self.power_name))

            # If there are more owned supply centres than units, build more units
            if owned_scs_count > units_count:
                # Calculate the number of units to build
                units_to_build = owned_scs_count - units_count
                possible_builds = []
                for loc in orderable_locations:
                    for order in possible_orders[loc]:
                        # Only get building orders
                        if 'B' in order:
                            # Get the minimum distance for each unit from any enemy supply centre
                            graph = self.map_graph_army if order[0] == "A" else self.map_graph_navy
                            _, dist = self.get_min_dist(graph, source=order.split(" ")[1])
                            possible_builds.append((dist, order))

                # Build the units with the closest proximity to enemy supply centres
                orders = []
                locations = set()
                for build in sorted(possible_builds, key=lambda x:x[0], reverse=True):
                    loc = build[1].split(" ")[1]
                    if loc not in locations:
                        locations.add(loc)
                        orders.append(build[1])
                return orders[:units_to_build]

            # If there are more units than supply centres, disband units by their distance to enemy supply centres
            if units_count > owned_scs_count:
                # Calculate the number of units to disband
                units_to_disband = units_count - owned_scs_count

                # Find all units that could potentially be disbanded
                possible_disbands = []
                for unit in self.game.get_units(self.power_name):
                    # Extract the components from the unit
                    unit_split = unit.split(" ", 1)
                    unit_type, unit_loc = unit_split[0], unit_split[1]

                    # Get the minimum distance for each unit from any enemy supply centre
                    graph = self.map_graph_army if unit_type == "A" else self.map_graph_navy
                    _, dist = self.get_min_dist(graph, source=[unit_loc])
                    possible_disbands.append((dist, unit))
                
                # Disband the units with the largest distance from any enemy supply centre 
                orders = []
                for order in sorted(possible_disbands, key=lambda x:x[0], reverse=True)[:units_to_disband]:
                    orders.append(f"{order[1]} D")
                return orders





        # If any armies can be in a convoy, take them to the nearest supply centre
        convoy_paths = self.game.convoy_paths_possible
        
        # If the current phase is the adjustment phase, place new items as close to the nearest enemy supply centre as possible
        if self.game.phase_type == 'A' and len(orderable_locations) > 0:
            closest_sc, unit_type = self.get_closest_sc()

            # Return the random orderable locations if there is no closest supply center
            if not closest_sc: return [random.choice(possible_orders[loc]) for loc in orderable_locations] # Taken from the random agent

            # Return the closest location
            if unit_type == "A": return [f"A {closest_sc} B"]
            else: return [f"F {closest_sc} B"]

        orders = []

        # If any countries have more supply centers, make armies target them
        owned_sc_count = len(self.game.get_centers(self.power_name))
        if owned_sc_count < self._previous_scs:
            # Identify the country with the maximum supply centers
            max_country = None
            other_powers = [i for i in self.game.map.powers if i != self.power_name]
            for power in other_powers:
                if owned_sc_count <= len(self.game.get_centers(power)): max_country = power

            if max_country:
                possible_orders = []
                for loc in orderable_locations:
                    possible_orders = [i for i in possible_orders[loc] if i[0] == "A"]
                closest_sc, unit = self.target_country(max_country, possible_orders)
                orders.append(f"A - {closest_sc}")
            
            return orders

        # If no special strategies need to be taken, greedily move to the closest enemy supply centre
        orders = [random.choice(possible_orders[loc]) for loc in orderable_locations if possible_orders[loc]]

        # If any unit cannot move, hold that unit
        for loc in orderable_locations:
            in_orders = False
            for order in orders:
                if loc in order: in_orders = True
            if not in_orders: orders.append(f"{loc} H")
        
        # Update previous supply centers
        self._previous_scs = owned_sc_count

        return orders
    
    def get_min_dist(self, graph, source, targets=None):
        closest_target, min_dist = None, float('inf')

        # If no targets are specified, use the enemy supply centres
        targets = set(self.game.map.scs) - set(self.game.get_centers(self.power_name))

        # Iterate over all orderable locations and find the minimum distance to any of the supplied targets
        possible_locations = self.game.get_all_possible_orders()
        for i, loc in enumerate(targets):
            path = nx.shortest_path(graph, source)
            if loc in path.keys() and len(path[loc]) < min_dist:
                closest_target = loc
                min_dist = len(path[source])
                
        return closest_target, min_dist
    
    def target_country(self, country, locations):
        # Retrieve the country's supply centres
        country_scs = self.game.get_centers(country)

        # Return the closest location to get to their supply 
        return self.get_closest_sc(country_scs, locations)

        '''
        Return a list of orders. Each order is a string, with specific format. For the format, read the game rule and game engine documentation.
        
        Expected format:
        A LON H                  # Army at LON holds
        F IRI - MAO              # Fleet at IRI moves to MAO (and attack)
        A WAL S F LON            # Army at WAL supports Fleet at LON (and hold)
        F NTH S A EDI - YOR      # Fleet at NTH supports Army at EDI to move to YOR
        F NWG C A NWY - EDI      # Fleet at NWG convoys Army at NWY to EDI
        A NWY - EDI VIA          # Army at NWY moves to EDI via convoy
        A WAL R LON              # Army at WAL retreats to LON
        A LON D                  # Disband Army at LON
        A LON B                  # Build Army at LON
        F EDI B                  # Build Fleet at EDI

        Note: If an invalid order is sent to the engine, it will be accepted but with a result of 'void' (no effect).
        Note: For a 'support' action, two orders are needed, one for the supporter and one for the supportee. (Same for 'convoy')
        Note: For each unit, if no order is given, it will 'hold' by default.

        Useful Functions:
        
        # This is a dict of all the possible orders for each unit at each location (for all powers).
        possible_orders = self.game.get_all_possible_orders()

        # This is a list of all orderable locations for the power you control.
        orderable_locations = self.game.get_orderable_locations(self.power_name)
    
        # Combining these two, you can have the full action space for the power you control.

        # You can re-use the build_map_graphs function in the GreedyAgent to build the connection graph of the map if needed.
        
        '''