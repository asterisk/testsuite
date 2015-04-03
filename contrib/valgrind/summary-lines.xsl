<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<!--
	The XML output of this stylesheet is used internally for producing
	text based summary.  The output is processed by runtests.py,
	TestRun._process_valgrind.
-->

<xsl:template match="/valgrindoutput">
	<xml>
		<xsl:if test="error | suppcounts/pair">
			<line>Valgrind <xsl:value-of select="tool" /> results<xsl:if test="usercomment"> - <xsl:value-of select="usercomment" /></xsl:if></line>
			<line />
		</xsl:if>
		<xsl:if test="error/what">
			<line>================= Errors ==================</line>
			<xsl:for-each select="error[what]">
				<cols>
					<xsl:attribute name="col1"><xsl:value-of select="kind"/></xsl:attribute>
					<xsl:attribute name="col2"><xsl:value-of select="what"/></xsl:attribute>
				</cols>
			</xsl:for-each>
			<line />
		</xsl:if>
		<xsl:if test="error/xwhat/leakedbytes">
			<line>============== Leaked Memory ==============</line>
			<xsl:if test="error[kind='Leak_DefinitelyLost']/xwhat/leakedbytes">
				<cols col1="Definitely Lost">
					<xsl:attribute name="col2">
						<xsl:value-of select="sum(error[kind='Leak_DefinitelyLost']/xwhat/leakedbytes | error[kind='Leak_IndirectlyLost']/xwhat/leakedbytes)" /> bytes
					</xsl:attribute>
				</cols>
			</xsl:if>
			<xsl:if test="error[kind='Leak_PossiblyLost']/xwhat/leakedbytes">
				<cols col1="Possible Lost">
					<xsl:attribute name="col2">
						<xsl:value-of select="sum(error[kind='Leak_PossiblyLost']/xwhat/leakedbytes)" /> bytes
					</xsl:attribute>
				</cols>
			</xsl:if>
			<xsl:if test="error[kind='Leak_StillReachable']/xwhat/leakedbytes">
				<cols col1="Reachable Memory">
					<xsl:attribute name="col2">
						<xsl:value-of select="sum(error[kind='Leak_StillReachable']/xwhat/leakedbytes)" /> bytes
					</xsl:attribute>
				</cols>
			</xsl:if>
			<line />
		</xsl:if>
		<xsl:if test="suppcounts/pair">
			<line>============== Suppressions ===============</line>
			<xsl:for-each select="suppcounts/pair">
				<cols>
					<xsl:attribute name="col1"><xsl:value-of select="count" /></xsl:attribute>
					<xsl:attribute name="col2"><xsl:value-of select="name" /></xsl:attribute>
				</cols>
			</xsl:for-each>
			<line/>
		</xsl:if>
	</xml>
</xsl:template>

</xsl:stylesheet>
