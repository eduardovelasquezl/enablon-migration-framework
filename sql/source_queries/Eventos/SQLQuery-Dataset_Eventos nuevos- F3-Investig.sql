SELECT        ITP_INFORME_INV2.IDEvento, ITP_INFORME_INV2_FASE3.IDInfFase3, ITP_INFORME_INV2_FASE3.IDInformeInv, format( ITP_INFORME_INV2_FASE3.FechaEnvioFase,   'dd/MM/yyyy HH:mm:ss')  as FechaEnvioFase, ITP_INFORME_INV2_FASE3.Pregunta1, 
                         ITP_INFORME_INV2_FASE3.Pregunta2, ITP_INFORME_INV2_FASE3.Pregunta3, ITP_INFORME_INV2_FASE3.Pregunta4, ITP_INFORME_INV2_FASE3.Pregunta5, ITP_INFORME_INV2_FASE3.PorQue1, 
                         ITP_INFORME_INV2_FASE3.PorQue2, ITP_INFORME_INV2_FASE3.PorQue3, ITP_INFORME_INV2_FASE3.PorQue4, ITP_INFORME_INV2_FASE3.PorQue5, ITP_INFORME_INV2_FASE3.ActosProcedimientos, 
                         ITP_INFORME_INV2_FASE3.ActosHerramientas, ITP_INFORME_INV2_FASE3.ActosMetodosProteccion, ITP_INFORME_INV2_FASE3.ActosConcienciaRiesgo, ITP_INFORME_INV2_FASE3.CondicionesProteccion, 
                         ITP_INFORME_INV2_FASE3.CondicionesHerramientas, ITP_INFORME_INV2_FASE3.CondicionesPeligroLugar, ITP_INFORME_INV2_FASE3.CondicionesOrganizacion, ITP_INFORME_INV2_FASE3.ConsultadoResponsableAC, 
                         ITP_INFORME_INV2_FASE3.FormacionArbolCausas, ITP_INFORME_INV2_FASE3.Liderazgo, ITP_INFORME_INV2_FASE3.ReglasYNormas, ITP_INFORME_INV2_FASE3.Competencias, ITP_INFORME_INV2_FASE3.Implantacion, 
                         ITP_INFORME_INV2_FASE3.PartesImplicadas, ITP_INFORME_INV2_FASE3.EvaluacioRiesgos, ITP_INFORME_INV2_FASE3.Registros, ITP_INFORME_INV2_FASE3.ManualesYPro, ITP_INFORME_INV2_FASE3.VarOPYRelevos, 
                         ITP_INFORME_INV2_FASE3.Interfaces, ITP_INFORME_INV2_FASE3.EstandaresPTS, ITP_INFORME_INV2_FASE3.GestionCambios, ITP_INFORME_INV2_FASE3.PTAMarcha, ITP_INFORME_INV2_FASE3.PrepEmerg, 
                         ITP_INFORME_INV2_FASE3.InspYMto, ITP_INFORME_INV2_FASE3.ElemCriticos, ITP_INFORME_INV2_FASE3.PermTrabajo, ITP_INFORME_INV2_FASE3.Contratista, ITP_INFORME_INV2_FASE3.Investigacion, 
                         ITP_INFORME_INV2_FASE3.Participante, ITP_INFORME_INV2_FASE3.Auditorias
FROM            ITP_INFORME_INV2 INNER JOIN
                         ITP_INFORME_INV2_FASE3 ON ITP_INFORME_INV2.IDInformeInv = ITP_INFORME_INV2_FASE3.IDInformeInv