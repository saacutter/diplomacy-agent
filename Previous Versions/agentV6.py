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
        self._targets = {power: 5 for power in self.game.powers if power != self.power_name}
        self._previous_orders = []

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
        orders = []
        ordered_locs = {}
        ordered_units = {unit.split("/")[0]: None for unit in self.game.get_units(self.power_name)}

        # Movement phase
        if self.game.phase_type == 'M':
            # If any supply centre was stolen, attack the country that stole it
            owned_scs_count = len(self.game.get_centers(self.power_name))
            other_powers = [i for i in self.game.map.powers if i != self.power_name]
            if owned_scs_count < self._previous_scs:
                # Identify the supply centres lost
                losses = self.game.lost
                lost_scs = []
                for sc in losses:
                    if losses[sc].name == self.power_name:
                        lost_scs.append(sc)
                
                # Find the countries that claimed the lost supply centres
                if lost_scs:
                    targets = []
                    for power in other_powers:
                        for sc in lost_scs:
                            if sc in self.game.get_centers(power):
                                targets.append(power)
                                break

                    # Adjust the weighting towards each country
                    for power in self._targets:
                        if power in targets: self._targets[power] = max(0.5, self._targets[power] - sum(i == power for i in targets)/5) # Heavily penalise by the amount of supply centres taken by that power, to a minimum of 0
                        else: self._targets[power] += 0.1 # Softly relax the weighting of countries that are not currently targeting us
            else:
                # Relax weighting for powers not targeting us
                for power in self._targets:
                    self._targets[power] += 0.1


            # If the current power is England and the game is in the early phases, heavily favour convoys to leave as soon as possible
            #if self.power_name == "ENGLAND" and ("1901" in phase or "1902" in phase):
            #    ...


            # If any units are at unowned supply centres in spring, hold them (because supply centres can only be captured in fall phases)
            phase = self.game.phase
            if "SPRING" in phase:
                for loc in orderable_locations:
                    for order in possible_orders[loc]:
                        if " S " not in order:
                            graph = self.map_graph_army if order[0] == "A" else self.map_graph_navy
                            _, dist = self.get_min_dist(graph, order.split(" ")[1], can_hold=True)
                            if dist == 0 and ordered_units[loc] is None: # Make the army hold if their closest enemy supply centre is 0 units away (indicating that they are already there)
                                orders.append(f"{loc} H")
                                ordered_locs[loc] = ordered_locs.get(loc, []) + [f"{loc} H"]
                                ordered_units[loc] = f"{loc} H"


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

                # Check if the fleet is near a coastline
                closest_sc, _ = self.get_min_dist(self.map_graph_navy, dest, targets=self.game.map.loc_coasts[dest])
                if closest_sc and ordered_units[fleet[:5]] is None and fleet not in self._previous_orders:
                    ordered_locs[dest] = ordered_locs.get(dest, []) + [fleet]
                    orders.append(fleet)
                    ordered_units[fleet[:5]] = fleet


            # Identify the country with the most supply centres
            max_country = None
            for power in other_powers:
                if owned_scs_count < len(self.game.get_centers(power)): max_country = power

            # If any countries have more supply centers, make armies target them
            if max_country:
                # Find all orders that armies can take
                possible_army_orders = []
                for loc in orderable_locations:
                    possible_army_orders += [i for i in possible_orders[loc] if i[0] == "A" and " - " in i and "S" not in i and "VIA" not in i] # Ignore support and convoy actions
                    
                # Retrieve the country's supply centres
                country_scs = self.game.get_centers(max_country)

                # Put each army on a path to that country
                for order in possible_army_orders:
                    closest_sc, _ = self.get_min_dist(self.map_graph_army, order.split(" ")[1], targets=country_scs)
                    ordered_unit = order[:5]
                    order = order.split(" ")
                    if closest_sc and ordered_units[ordered_unit] is None and f"{order[0]} {order[1]} - {closest_sc}" not in self._previous_orders:
                        orders.append(f"{order[0]} {order[1]} - {closest_sc}")
                        ordered_locs[closest_sc] = ordered_locs.get(closest_sc, []) + [f"{order[0]} {order[1]} - {closest_sc}"]
                        ordered_units[ordered_unit] = f"{order[0]} {order[1]} - {closest_sc}"


            # If no special strategies need to be taken, greedily move to the closest enemy supply centre
            for loc in orderable_locations:
                for order in possible_orders[loc]:
                    graph = self.map_graph_army if order[0] == "A" else self.map_graph_navy
                    closest_sc, _ = self.get_min_dist(graph, order.split(" ")[1])
                    ordered_unit = order[:5]
                    order = order.split(" ")
                    if closest_sc and ordered_units[ordered_unit] is None and f"{order[0]} {order[1]} - {closest_sc}" not in self._previous_orders:
                        orders.append(f"{order[0]} {order[1]} - {closest_sc}")
                        ordered_locs[closest_sc] = ordered_locs.get(closest_sc, []) + [f"{order[0]} {order[1]} - {closest_sc}"]
                        ordered_units[ordered_unit] = f"{order[0]} {order[1]} - {closest_sc}"

            
            # Identify if any units can support other units if they are heading to the same destination (prevents bounces)
            supported_units = []
            for loc in ordered_locs:
                if len(ordered_locs[loc]) > 1:
                    for i in range(len(ordered_locs[loc]) - 1):
                        unit1 = ordered_locs[loc][i]
                        unit2 = ordered_locs[loc][i + 1]
                        if unit1 != unit2:
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
                            else: # Randomly select which order to remove (for some variety)
                                if random.randint(1, 2) == 1:
                                    try: orders.remove(unit1)
                                    except: ...
                                    orders.append(f"{unit1_split[0]} {unit1_split[1]} S {unit2}")
                                    supported_units.append(unit2_unit)
                                else:
                                    try: orders.remove(unit2)
                                    except: ...
                                    orders.append(f"{unit2_split[0]} {unit2_split[1]} S {unit1}")
                                    supported_units.append(unit1_unit)


            # If the current orders is equal to the previous orders (indicating that a loop is possible), randomly select some valid moves (suboptimal, but means more moves can be played)
            if orders == self._previous_orders:
                for order in orders.copy():
                    if random.randint(1, 10) == 1: # 10% chance to randomly select any move
                        orders.remove(order)
                        loc = order.split(" ")[1]
                        chosen_order = random.choice(possible_orders[loc])
                        orders.append(chosen_order)
                        ordered_units[f"{order[0]} {loc}"] = chosen_order

            for unit in ordered_units:
                if ordered_units[unit] is None:
                    loc = unit.split(" ")[1]
                    possibilities = [order for order in possible_orders[loc] if " - " in order and " S " not in order]
                    closest_sc, min_dist = None, float('inf')
                    graph = self.map_graph_army if unit[0] == "A" else self.map_graph_navy
                    for order in possibilities:
                        _, dist = self.get_min_dist(graph, order.split(" ")[-1])
                        if dist and dist < min_dist:
                            min_dist = dist
                            closest_sc = order
                    if closest_sc:
                        orders.append(closest_sc)


            # Update previous supply centers
            self._previous_scs = owned_scs_count

            # Update the previous orders
            self._previous_orders = orders
        


        # Retreat phase
        elif self.game.phase_type == 'R':
            # Identify any possible retreats
            for loc in orderable_locations:
                possible_retreats = [order for order in possible_orders[loc] if " R " in order] # Get all possible retreat orders
                if possible_retreats:
                    for retreat in possible_retreats:
                        graph = self.map_graph_army if retreat[0] == "A" else self.map_graph_navy
                        closest_sc, _ = self.get_min_dist(graph, retreat.split(" ")[2]) # Use target destination as source
                        if closest_sc:
                            orders.append(retreat)
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
                            # Get the minimum distance for each unit from any enemy supply centre
                            if order[0] == "A":
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
                
                # Disband the units with the largest distance from any enemy supply centre or the most isolated (prioritising armies)
                for order in sorted(possible_disbands, key=lambda x:(-x[0], x[1][0]))[:units_to_disband]:
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
            # Get the power name that owns the target
            power = None
            for p in self.game.powers:
                if target in self.game.get_centers(p):
                    power = p
                    break

            if target in path.keys() and len(path[target]) < min_dist:
                if len(path[target]) > 1: # Ensure that there is a path that can be returned
                    closest_target = path[target][1]
                    min_dist = (len(path[target]) - 1)*self._targets.get(power, 1) # Get a weighted minimum distance based on power hostility (with a default of 1 to favour minimum distance)
                
                # If any of the targets is the source and a hold can be requested, return the target
                if can_hold and target == source: return target, 0
                
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