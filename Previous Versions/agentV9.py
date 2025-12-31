import time
import timeout_decorator
from agent_baselines import Agent
import networkx as nx

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
        self._targets = {power: 5 for power in self.game.powers if power != self.power_name}
        self.current_pos = {}

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
        # Generate necessary information to coordinate movement
        possible_orders = self.game.get_all_possible_orders()
        orderable_locations = self.game.get_orderable_locations(self.power_name)
        orders = []
        ordered_locs = {}
        ordered_units = {unit.split("/")[0]: None for unit in self.game.get_units(self.power_name)}
        self.current_pos = {loc for loc in orderable_locations}

        # Movement phase
        if self.game.phase_type == 'M':
            # If any supply centre was stolen, adjust the weighting towards the power that stole it
            owned_scs_count = len(self.game.get_centers(self.power_name))
            other_powers = [i for i in self.game.map.powers if i != self.power_name]
            if owned_scs_count < self._previous_scs:
                # Identify the supply centres lost
                losses = self.game.lost
                lost_scs = []
                for sc in losses:
                    if losses[sc].name == self.power_name:
                        lost_scs.append(sc)
                
                # Find the powers that claimed the lost supply centres
                if lost_scs:
                    targets = []
                    for sc in lost_scs:
                        for power in other_powers:
                            if sc in self.game.get_centers(power):
                                targets.append(power)
                                break

                    # Adjust the weighting towards each power based on this knowledge
                    for power in self._targets:
                        if power in targets: self._targets[power] = max(0.5, self._targets[power] - sum(i == power for i in targets)/5) # Heavily penalise by the amount of supply centres taken by that power, to a minimum of 0.5
                        else: self._targets[power] += 0.1 # Softly relax the weighting of countries that are not currently targeting us
            else:
                # Relax weighting for powers not targeting us
                for power in self._targets:
                    self._targets[power] += 0.1


            # If any units are at unowned supply centres, hold at them until they're captured
            for unit in self.game.get_units(self.power_name):
                graph = self.map_graph_army if unit[0] == "A" else self.map_graph_navy # Identify the relevant graph
                _, dist = self.get_min_dist(graph, unit.split(" ")[1], can_hold=True) # Allow the minimum distance to be 0 (indicating that the unit is in a supply centre)
                if dist == 0 and ordered_units[unit] is None: # Make the unit hold if their closest enemy supply centre is 0 units away (indicating that they are already there)
                    orders.append(f"{unit} H")
                    ordered_locs[unit] = ordered_locs.get(unit, []) + [f"{unit} H"]
                    ordered_units[unit] = f"{unit} H"


            # Identify any convoys that can be made
            possible_fleets = []
            for loc in orderable_locations:
                possible_fleets += [i for i in possible_orders[loc] if "VIA" in i or " C " in i]
            
            # If no other fleet is going to the same destination and it is heading towards a coast (allowing for convoys), let the fleet move
            for fleet in possible_fleets:
                # Extract the fleet's destination
                fleet_split = fleet.split(" ")
                if len(fleet_split) == 7: dest = fleet_split[-1]
                else: dest = fleet_split[-2]

                # Check if the fleet is near a coastline and head towards it if possible
                closest_sc, _ = self.get_min_dist(self.map_graph_navy, dest, targets=self.game.map.loc_coasts[dest])
                if closest_sc and ordered_units[fleet[:5]] is None:
                    orders.append(fleet)
                    ordered_locs[dest] = ordered_locs.get(dest, []) + [fleet]
                    ordered_units[fleet[:5]] = fleet


            # Identify the power with the most supply centres
            max_power = None
            for power in other_powers:
                if owned_scs_count < len(self.game.get_centers(power)): max_power = power

            # If any countries have more supply centers, make armies target them
            if max_power:
                # Adjust that power's weighting
                self._targets[max_power] = max(0.5, self._targets[max_power] - (owned_scs_count + len(self.game.get_centers(max_power))/5))

                # Find all orders that armies can take
                possible_army_orders = []
                for loc in orderable_locations:
                    possible_army_orders += [i for i in possible_orders[loc] if i[0] == "A" and " - " in i and " S " not in i and " VIA" not in i] # Ignore support and convoy actions
                    
                # Retrieve the power's supply centres
                power_scs = self.game.get_centers(max_power)

                # Put each army on a path to that power
                for order in possible_army_orders:
                    closest_sc, _ = self.get_min_dist(self.map_graph_army, order.split(" ")[1], targets=power_scs) # Gets the next closest supply centre owned by that power
                    ordered_unit = order[:5]
                    if closest_sc and ordered_units[ordered_unit] is None:
                        order = order.split(" ")
                        orders.append(f"{order[0]} {order[1]} - {closest_sc}")
                        ordered_locs[closest_sc] = ordered_locs.get(closest_sc, []) + [f"{order[0]} {order[1]} - {closest_sc}"]
                        ordered_units[ordered_unit] = f"{order[0]} {order[1]} - {closest_sc}"


            # If no special strategies need to be taken, greedily move to the closest enemy supply centre
            for loc in orderable_locations:
                for order in possible_orders[loc]:
                    graph = self.map_graph_army if order[0] == "A" else self.map_graph_navy # Identify the relevant graph to check
                    closest_sc, _ = self.get_min_dist(graph, order.split(" ")[1])
                    ordered_unit = order[:5]
                    if closest_sc and ordered_units[ordered_unit] is None:
                        order = order.split(" ")
                        orders.append(f"{order[0]} {order[1]} - {closest_sc}")
                        ordered_locs[closest_sc] = ordered_locs.get(closest_sc, []) + [f"{order[0]} {order[1]} - {closest_sc}"]
                        ordered_units[ordered_unit] = f"{order[0]} {order[1]} - {closest_sc}"

            
            # Identify if any units can support other units if they are heading to the same destination and create a support order (prevents bounces)
            supported_units = []
            for loc in ordered_locs:
                if len(ordered_locs[loc]) > 1: # Check if more than one unit is heading to the same location
                    for i in range(len(ordered_locs[loc]) - 1):
                        unit1 = ordered_locs[loc][i]
                        unit2 = ordered_locs[loc][i + 1]
                        if unit1[:5] != unit2[:5]: # Ensure that the units are not the same
                            unit1_split = unit1.split(" ")
                            unit2_split = unit2.split(" ")
                            unit1_dest = unit1_split[-1]
                            unit1_unit = f"{unit1_split[0]} {unit1_split[1]}"
                            unit2_dest = unit2_split[-1]
                            unit2_unit = f"{unit2_split[0]} {unit2_split[1]}"

                            # If either unit is already being supported, ensure that all other units also support it (increases attack power)
                            if unit1_unit in supported_units:
                                try: orders.remove(unit2)
                                except: ...
                                orders.append(f"{unit2_split[0]} {unit2_split[1]} S {unit1}")
                            elif unit2_unit in supported_units:
                                try: orders.remove(unit1)
                                except: ...
                                orders.append(f"{unit1_split[0]} {unit1_split[1]} S {unit2}")
                            else: # If no unit is being supported, use unit 1 (arbitrary)
                                try: orders.remove(unit1)
                                except: ...
                                orders.append(f"{unit1_split[0]} {unit1_split[1]} S {unit2}")
                                supported_units.append(unit2_unit)

            
            # If there is any unit without an order, select one for it
            for unit in ordered_units:
                if ordered_units[unit] is None:
                    # Extract the current location of the unit and generate the possible moves it could take
                    loc = unit.split(" ")[1]
                    possibilities = [order for order in possible_orders[loc] if " - " in order and " S " not in order]

                    # Locate the nearest target for the unit to move to
                    closest_sc, min_dist = None, float('inf')
                    graph = self.map_graph_army if unit[0] == "A" else self.map_graph_navy
                    for order in possibilities:
                        _, dist = self.get_min_dist(graph, order.split(" ")[-1])
                        if dist and dist < min_dist:
                            min_dist = dist
                            closest_sc = order
                    
                    # If a nearest target could be found, head to it
                    if closest_sc:
                        orders.append(closest_sc)


            # If there is an order that was bounced in the last phase and attempts to make the same move, try and make a move for an adjacent position
            for order in orders.copy():
                unit = order.split(" ")[0] + " " + order.split(" ")[1]
                if "bounce" in self.game.get_order_status(self.power_name, unit) and " - " in order: # Only consider orders that bounced that moved units (including supports and convoys)
                    adjacent_positions = self.game.map.abut_list(unit[2:]) # Find the adjacent positions to the unit
                    for position in adjacent_positions:
                        if position not in ordered_locs and position not in self.current_pos: # Only consider adjacent position that are not currently ordered or were occupied at the start of the order
                            if (order[0] == "A" and not self.game.map.abuts("A", unit[2:], "-", position)) or (order[0] == "F" and not self.game.map.abuts("F", unit[2:], "-", position)): continue # Ignore invalid orders
                            orders.append(f"{unit} - {position}")
                            orders.remove(order)
                            break


            # Update previous supply centers
            self._previous_scs = owned_scs_count
        


        # Retreat phase
        elif self.game.phase_type == 'R':
            # Identify any possible retreats
            for loc in orderable_locations:
                possible_retreats = [order for order in possible_orders[loc] if " R " in order] # Get all possible retreat orders

                # If retreat orders could be found, make it retreat if it puts it into a good position
                if possible_retreats:
                    for retreat in possible_retreats:
                        graph = self.map_graph_army if retreat[0] == "A" else self.map_graph_navy
                        closest_sc, _ = self.get_min_dist(graph, retreat.split(" ")[3]) # Use target destination as source
                        unit = retreat[:5]
                        if closest_sc and ((unit in ordered_units and ordered_units[unit] is None) or ("\*" + unit in ordered_units and ordered_units[unit] is None)):
                            orders.append(retreat)
                            ordered_units[unit] = retreat
                else:
                    orders.append(f"{loc} D") # If the unit cannot retreat, it must be disbanded
        


        # Adjustment phase
        elif self.game.phase_type == 'A':
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
                        if " B" in order: # Only get build orders
                            if order[0] == "A": # Get the minimum distance for each army from any owned supply centre
                                _, dist = self.get_min_dist(self.map_graph_army, order.split(" ")[1], targets=self.game.get_centers(self.power_name))
                                if dist: possible_builds.append((dist, order))
                            else: # If the build is a fleet, place them near unit coastlines
                                source = order.split(" ")[1]
                                _, dist = self.get_min_dist(self.map_graph_navy, source, targets=self.game.map.loc_coasts[source] + self.game.get_centers(self.power_name))
                                if dist: possible_builds.append((dist, order))

                # Build the units with the closest proximity to enemy supply centres
                locations = set(unit.split(" ")[1] for power in self.game.powers for unit in self.game.get_units(power)) # Add already occupied regions to set to avoid building in an occupied unit
                for _, order in sorted(possible_builds, key=lambda x:x[0]):
                    loc = order.split(" ")[1].split("/")[0] # Ensures that STP/SC and STP/NC cannot both be selected (as selecting both would be invalid)
                    if loc not in locations:
                        locations.add(loc)
                        orders.append(order)
                return orders[:units_to_build]


            # If there are more units than supply centres, disband units by their distance to enemy supply centres
            elif units_count > owned_scs_count:
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
                    unit_locs = [i.split(" ")[1] for i in self.game.get_units(self.power_name)]

                    # Identify if a unit is far from an enemy supply centre or is isolated
                    _, enemy_dist = self.get_min_dist(graph, unit_loc) 
                    _, unit_dist = self.get_min_dist(graph, unit_loc, targets=unit_locs + self.game.get_centers(self.power_name))
                    dist = enemy_dist if enemy_dist > unit_dist else unit_dist

                    possible_disbands.append((dist, unit))
                
                # Disband the units with the largest distance from any enemy supply centre or the most isolated (prioritising fleets)
                for order in sorted(possible_disbands, key=lambda x:(x[0], x[1][0]), reverse=True)[:units_to_disband]:
                    orders.append(f"{order[1]} D")
                return orders
        return orders
    
    def get_min_dist(self, graph, source, targets=None, can_hold=False):
        closest_target, min_dist = None, float('inf')

        # If no targets are specified, use the enemy supply centres
        if not targets: targets = set(self.game.map.scs) - set(self.game.get_centers(self.power_name))

        # Attempt to find a path from the source
        try:
            path = nx.shortest_path(graph, source) # Generate the shortest path between the source and all other nodes
        except:
            return None, None
        
        # Iterate over all targets and find the minimum distance from the source
        for target in targets:
            # If any of the targets is the source and a hold can be requested, return the target
            if can_hold and target == source: return target, 0

            # Get the power name that owns the target
            power = None
            for p in self.game.powers:
                if target in self.game.get_centers(p):
                    power = p
                    break
            
            # If there is a path from the source to the target and it has a shorter distance than any other path so far, use itr
            if target in path.keys() and len(path[target]) < min_dist:
                if len(path[target]) > 1 and path[target][1] not in self.current_pos: # Ensure that there is a path that can be returned
                    closest_target = path[target][1]
                    min_dist = (len(path[target]) - 1)*self._targets.get(power, 1) # Get a weighted minimum distance based on power hostility (with a default of 1 to favour minimum distance)
                
        return closest_target, min_dist

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