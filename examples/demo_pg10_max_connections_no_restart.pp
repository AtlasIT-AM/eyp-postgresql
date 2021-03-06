class { 'postgresql':
  wal_level           => 'hot_standby',
  max_wal_senders     => '3',
  checkpoint_segments => '8',
  wal_keep_segments   => '8',
  version             => '10',
  max_connections     => '300',
  restart_if_needed   => false,
}

postgresql::pgdumpbackup { 'demobackup':
  destination => '/tmp',
}

postgresql::hba_rule { 'demo':
  user     => 'demo',
  database => 'demo',
  address  => '192.168.0.0/16',
}

postgresql::role { 'demo':
  password    => 'demopass',
}
