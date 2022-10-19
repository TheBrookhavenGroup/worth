# worth

Simple trading bookkeeping system.


### GPG for IB FTP

`brew install gunpg`
`gpg --full-generate-key`

Use RSA 2048

To produce ascii public key to send to IB:
`gpg --output ~/mygpg.key --armor --export <email>`

To encrypt a file named foo.txt:
`gpg --encrypt --sign --armor -r <email> foo.txt`

That results in `foo.txt.asc`.  To decrypt:
`gpg foo.txt.asc`