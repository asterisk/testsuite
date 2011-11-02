BEGIN TRANSACTION;
CREATE TABLE sipfriends (name varchar(15) NOT NULL, secret varchar(63) NOT NULL DEFAULT "", type varchar(15) NOT NULL DEFAULT "friend", host varchar(63) NOT NULL DEFAULT "dynamic", ipaddr varchar(63) NOT NULL DEFAULT "", port int unsigned default NULL DEFAULT 5060, insecure varchar(11) NOT NULL DEFAULT "", commented INTEGER NOT NULL DEFAULT 0);
INSERT INTO sipfriends VALUES('test1','','friend','127.0.0.1','',5061,'',0);
INSERT INTO sipfriends VALUES('test2','','friend','dynamic','127.0.0.2',5061,'',0);
INSERT INTO sipfriends VALUES('test3','','friend','127.0.0.3','',666,'port',0);
INSERT INTO sipfriends VALUES('test4','','friend','dynamic','127.0.0.4',666,'port',0);
CREATE TABLE sipregs (name varchar(15) NOT NULL, ipaddr varchar(15) NOT NULL DEFAULT "", port int unsigned NOT NULL DEFAULT 5060, defaultuser varchar(15) NOT NULL DEFAULT "", fullcontact varchar(63) NOT NULL DEFAULT "", regserver varchar(63) NOT NULL DEFAULT "", useragent varchar(63) NOT NULL DEFAULT "", insecure varchar(11) NOT NULL DEFAULT "", lastms int unsigned NOT NULL DEFAULT 0, regseconds int unsigned NOT NULL DEFAULT 0, commented INTEGER NOT NULL DEFAULT 0);
INSERT INTO sipregs VALUES('test1-fail','127.0.0.1',5061,'','','','','',0,0,0);
COMMIT;
