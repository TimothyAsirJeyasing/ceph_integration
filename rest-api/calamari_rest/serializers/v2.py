from cStringIO import StringIO

from rest_framework import serializers
from rest_framework.parsers import JSONParser
from calamari_common.db.event import severity_str
import calamari_rest.serializers.fields as fields
from calamari_common.types import CRUSH_RULE_TYPE_REPLICATED, CRUSH_RULE_TYPE_ERASURE, USER_REQUEST_COMPLETE, \
    USER_REQUEST_SUBMITTED, OSD_FLAGS


class ValidatingSerializer(serializers.Serializer):
    class Meta:
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    def __init__(self, instance=None, data=None, **kwargs):
        if data is not None:
            data = JSONParser().parse(StringIO(data))

        super(ValidatingSerializer, self).__init__(instance, data, **kwargs)

    def is_valid(self, http_method):

        self._errors = super(ValidatingSerializer, self).errors or {}

        if self.init_data is not None:
            if http_method is 'PUT':
                self._errors.update(self.construct_errors(self.Meta.create_allowed,
                                                          self.Meta.create_required,
                                                          self.init_data.keys(),
                                                          http_method))

            elif http_method in ('PATCH', 'POST'):
                self._errors.update(self.construct_errors(self.Meta.modify_allowed,
                                                          self.Meta.modify_required,
                                                          self.init_data.keys(),
                                                          http_method))
            else:
                self._errors.update([[http_method, 'Not a valid method']])

        return not self._errors

    def construct_errors(self, allowed, required, init_data, action):
        errors = {}

        not_allowed = set(init_data) - set(allowed)
        errors.update(dict([x, 'Not allowed during %s' % action] for x in not_allowed))

        required = set(required) - set(init_data)
        errors.update(dict([x, 'Required during %s' % action] for x in required))

        return errors

        '''
        readonly = [x for x,y in self.fields.items() if y.read_only]
        readonly_fields = dict([(x, 'This field is read_only') for x in set(self.init_data.keys()) & set(readonly)])
        '''

class ClusterSerializer(ValidatingSerializer):
    class Meta:
        fields = ('update_time', 'id', 'name')
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    update_time = serializers.DateTimeField(
        help_text="The time at which the last status update from this cluster was received"
    )
    name = serializers.Field(
        help_text="Human readable cluster name, not a unique identifier"
    )
    id = serializers.Field(
        help_text="The FSID of the cluster, universally unique"
    )


class PoolSerializer(ValidatingSerializer):
    class Meta:
        fields = ('name', 'id', 'size', 'pg_num', 'crush_ruleset', 'min_size', 'crash_replay_interval', 'crush_ruleset',
                  'pgp_num', 'hashpspool', 'full', 'quota_max_objects', 'quota_max_bytes')
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    # Required in creation
    name = serializers.CharField(source='pool_name',
                                 help_text="Human readable name of the pool, may"
                                 "change over the pools lifetime at user request.")
    pg_num = serializers.IntegerField(
        help_text="Number of placement groups in this pool")

    # Not required in creation, immutable
    id = serializers.CharField(source='pool', required=False, help_text="Unique numeric ID")

    # May be set in creation or updates
    size = serializers.IntegerField(required=False,
                                    help_text="Replication factor")
    min_size = serializers.IntegerField(required=False,
                                        help_text="Minimum number of replicas required for I/O")
    crash_replay_interval = serializers.IntegerField(required=False,
                                                     help_text="Number of seconds to allow clients to "
                                                               "replay acknowledged, but uncommitted requests")
    crush_ruleset = serializers.IntegerField(required=False, help_text="CRUSH ruleset in use")
    # In 'ceph osd pool set' it's called pgp_num, but in 'ceph osd dump' it's called
    # pg_placement_num :-/
    pgp_num = serializers.IntegerField(source='pg_placement_num', required=False,
                                       help_text="Effective number of placement groups to use when calculating "
                                                 "data placement")

    # This is settable by 'ceph osd pool set' but in 'ceph osd dump' it only appears
    # within the 'flags' integer.  We synthesize a boolean from the flags.
    hashpspool = serializers.BooleanField(required=False, help_text="Enable HASHPSPOOL flag")

    # This is synthesized from ceph's 'flags' attribute, read only.
    full = serializers.BooleanField(required=False, help_text="True if the pool is full")

    quota_max_objects = serializers.IntegerField(required=False,
                                                 help_text="Quota limit on object count (0 is unlimited)")
    quota_max_bytes = serializers.IntegerField(required=False,
                                               help_text="Quota limit on usage in bytes (0 is unlimited)")


class OsdSerializer(ValidatingSerializer):
    class Meta:
        fields = ('uuid', 'up', 'in', 'id', 'reweight', 'server', 'pools', 'valid_commands', 'public_addr', 'cluster_addr')
        create_allowed = ()
        create_required = ()
        modify_allowed = ('up', 'in', 'reweight')
        modify_required = ()

    id = serializers.IntegerField(read_only=True, source='osd', help_text="ID of this OSD within this cluster")
    uuid = fields.UuidField(read_only=True, help_text="Globally unique ID for this OSD")
    up = fields.BooleanField(help_text="Whether the OSD is running from the point of view of the rest of the cluster")
    _in = fields.BooleanField(help_text="Whether the OSD is 'in' the set of OSDs which will be used to store data")
    reweight = serializers.FloatField(help_text="CRUSH weight factor")
    server = serializers.CharField(read_only=True, help_text="FQDN of server this OSD was last running on")
    pools = serializers.Field(help_text="List of pool IDs which use this OSD for storage")
    valid_commands = serializers.CharField(read_only=True, help_text="List of commands that can be applied to this OSD")

    public_addr = serializers.CharField(read_only=True, help_text="Public/frontend IP address")
    cluster_addr = serializers.CharField(read_only=True, help_text="Cluster/backend IP address")

# Declarative metaclass definitions are great until you want
# to use a reserved word
OsdSerializer.base_fields['in'] = OsdSerializer.base_fields['_in']


class OsdConfigSerializer(ValidatingSerializer):
    class Meta:
        fields = OSD_FLAGS
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    pause = serializers.BooleanField(help_text="Something helpful", required=False)
    noup = serializers.BooleanField(required=False)
    nodown = serializers.BooleanField(required=False)
    noout = serializers.BooleanField(required=False)
    noin = serializers.BooleanField(required=False)
    nobackfill = serializers.BooleanField(required=False)
    norecover = serializers.BooleanField(required=False)
    noscrub = serializers.BooleanField(required=False)
    nodeepscrub = serializers.BooleanField(required=False)


OsdConfigSerializer.base_fields['nodeep-scrub'] = OsdConfigSerializer.base_fields['nodeepscrub']


class CrushRuleSerializer(ValidatingSerializer):
    class Meta:
        fields = ('id', 'name', 'ruleset', 'type', 'min_size', 'max_size', 'steps', 'osd_count')
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    id = serializers.IntegerField(source='rule_id')
    name = serializers.CharField(source='rule_name', help_text="Human readable name")
    ruleset = serializers.IntegerField(help_text="ID of the CRUSH ruleset of which this rule is a member")
    type = fields.EnumField({CRUSH_RULE_TYPE_REPLICATED: 'replicated', CRUSH_RULE_TYPE_ERASURE: 'erasure'}, help_text="Data redundancy type")
    min_size = serializers.IntegerField(
        help_text="If a pool makes more replicas than this number, CRUSH will NOT select this rule")
    max_size = serializers.IntegerField(
        help_text="If a pool makes fewer replicas than this number, CRUSH will NOT select this rule")
    steps = serializers.Field(help_text="List of operations used to select OSDs")
    osd_count = serializers.IntegerField(help_text="Number of OSDs which are used for data placement")


class CrushRuleSetSerializer(ValidatingSerializer):
    class Meta:
        fields = ('id', 'rules')
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    id = serializers.IntegerField()
    rules = CrushRuleSerializer(many=True)


class RequestSerializer(ValidatingSerializer):
    class Meta:
        fields = ('id', 'state', 'error', 'error_message', 'headline', 'status', 'requested_at', 'completed_at')
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    id = serializers.CharField(help_text="A globally unique ID for this request")
    state = serializers.CharField(help_text="One of '{complete}', '{submitted}'".format(
        complete=USER_REQUEST_COMPLETE, submitted=USER_REQUEST_SUBMITTED))
    error = serializers.BooleanField(help_text="True if the request completed unsuccessfully")
    error_message = serializers.CharField(help_text="Human readable string describing failure if ``error`` is True")
    headline = serializers.CharField(help_text="Single sentence human readable description of the request")
    status = serializers.CharField(help_text="Single sentence human readable description of the request's current "
                                             "activity, if it has more than one stage.  May be null.")
    requested_at = serializers.DateTimeField(help_text="Time at which the request was received by calamari server")
    completed_at = serializers.DateTimeField(help_text="Time at which the request completed, may be null.")


class SaltKeySerializer(ValidatingSerializer):
    class Meta:
        fields = ('id', 'status')
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    id = serializers.CharField(help_text="The minion ID, usually equal to a host's FQDN")
    status = serializers.CharField(help_text="One of 'accepted', 'rejected' or 'pre'")


class ServiceSerializer(ValidatingSerializer):
    class Meta:
        fields = ('fsid', 'type', 'id', 'running')
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    fsid = serializers.SerializerMethodField("get_fsid")
    type = serializers.SerializerMethodField("get_type")
    id = serializers.SerializerMethodField("get_id")
    running = serializers.BooleanField()

    def get_fsid(self, obj):
        return obj['id'][0]

    def get_type(self, obj):
        return obj['id'][1]

    def get_id(self, obj):
        return obj['id'][2]


class SimpleServerSerializer(ValidatingSerializer):
    class Meta:
        fields = ('fqdn', 'hostname', 'managed', 'last_contact', 'boot_time', 'ceph_version', 'services')
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    # Identifying information
    fqdn = serializers.CharField(help_text="Fully qualified domain name")
    hostname = serializers.CharField(help_text="Unqualified hostname")

    # Calamari monitoring status
    managed = serializers.BooleanField(
        help_text="True if this server is under Calamari server's control, false"
                  "if the server's existence was inferred via Ceph cluster maps.")
    last_contact = serializers.DateTimeField(
        help_text="The time at which this server last communicated with the Calamari"
                  "server.  This is always null for unmanaged servers")
    boot_time = serializers.DateTimeField(
        help_text="The time at which this server booted. "
                  "This is always null for unmanaged servers")
    ceph_version = serializers.CharField(
        help_text="The version of Ceph installed.  This is always null for unmanaged servers."
    )
    # Ceph usage
    services = ServiceSerializer(many=True, help_text="List of Ceph services seen"
                                 "on this server")


class ServerSerializer(SimpleServerSerializer):
    class Meta:
        fields = ('fqdn', 'hostname', 'services', 'frontend_addr', 'backend_addr',
                  'frontend_iface', 'backend_iface', 'managed',
                  'last_contact', 'boot_time', 'ceph_version')
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    # Ceph network configuration
    frontend_addr = serializers.CharField()  # may be null if no OSDs or mons on server
    backend_addr = serializers.CharField()  # may be null if no OSDs on server
    frontend_iface = serializers.CharField()  # may be null if interface for frontend addr not up
    backend_iface = serializers.CharField()  # may be null if interface for backend addr not up


class EventSerializer(ValidatingSerializer):
    class Meta:
        fields = ('when', 'severity', 'message')
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    when = serializers.DateTimeField(help_text="Time at which event was generated")
    severity = serializers.SerializerMethodField('get_severity')
    # FIXME: django_rest_framework doesn't let me put help_text on a methodfield
    # help_text="Severity, one of %s" % ",".join(SEVERITIES.keys()))
    message = serializers.CharField(help_text="One line human readable description")

    def get_severity(self, obj):
        return severity_str(obj.severity)


class LogTailSerializer(ValidatingSerializer):
    """
    Trivial serializer to wrap a string blob of log output
    """
    class Meta:
        fields = ('lines',)
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    lines = serializers.CharField("Retrieved log data as a newline-separated string")


class ConfigSettingSerializer(ValidatingSerializer):
    class Meta:
        fields = ('key', 'value')
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    # This is very simple for now, but later we may add more things like
    # schema information, allowed values, defaults.

    key = serializers.CharField(help_text="Name of the configuration setting")
    value = serializers.CharField(help_text="Current value of the setting, as a string")


class MonSerializer(ValidatingSerializer):
    class Meta:
        fields = ('name', 'rank', 'in_quorum', 'server', 'addr')
        create_allowed = ()
        create_required = ()
        modify_allowed = ()
        modify_required = ()

    name = serializers.CharField(help_text="Human readable name")
    rank = serializers.IntegerField(help_text="Unique of the mon within the cluster")
    in_quorum = serializers.BooleanField(help_text="True if the mon is a member of current quorum")
    server = serializers.CharField(help_text="FQDN of server running the OSD")
    addr = serializers.CharField(help_text="IP address of monitor service")
