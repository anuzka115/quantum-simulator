class ProtocolHandler:
    def __init__(self, protocol_name, node_factory, channel_factory, run_function):
        self.protocol_name = protocol_name
        self.node_factory = node_factory
        self.channel_factory = channel_factory
        self.run_function = run_function
        self.qber=None
        self.asym_key_rate=None 
        self.node_objs = {} 

    def run(self, config):
        """
        config: dict with structure like:
        {
            "env": simpy.Environment(),
            "nodes": {
                "Alice": {"role": "Sender", "args": {...}},
                "Bob":   {"role": "Receiver", "args": {...}}
            },
            "channel": {
                "endpoints": ("Alice", "Bob"),
                "args": {...}
            },
            "protocol_args": {...}
        }
        """
        env = config["env"]
        #node_objs = {}
        
        for node_id, node_info in config["nodes"].items():
            role = node_info["role"]
            args = node_info["args"]
            self.node_objs[node_id] = self.node_factory(node_id, role, env, **args)
        node_names = list(config["nodes"].keys())
        a, b = node_names[0], node_names[1]
        channel=None
        if self.channel_factory is not None and "channel" in config:
            a, b = config["channel"]["endpoints"]
            channel_args = config["channel"]["args"]
            channel = self.channel_factory(a, b, **channel_args)


        

       # self.run_function(node_objs[a], node_objs[b], channel, env, **config.get("protocol_args", {}))
        self.qber, self.asym_key_rate = self.run_function(
            self.node_objs[a], self.node_objs[b], channel, env, **config.get("protocol_args", {})
        )
