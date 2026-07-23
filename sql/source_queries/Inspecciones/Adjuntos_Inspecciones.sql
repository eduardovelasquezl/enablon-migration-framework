SELECT [IDDocumento]
      ,[IDTipoInforme]
      ,[IDInforme]
      ,[IDCentro]
      ,[NombreFichero]
      ,[IDUsuarioGuardadoPor]
      ,format([FechaCreacion],  'dd/MM/yyyy HH:mm:ss') as FechaCreacion,
       [IDUsuarioRed]
      ,[IDTipoDocumento]
  FROM [Prevencion].[dbo].[ITP_DOCUMENTOS_ADJUNTOS] where IDTipoInforme =4
