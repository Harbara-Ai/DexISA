"""Legacy evaluation action surfaces; no changes to controllers or limits."""
from dex_hand.skills.shape_hand import ShapeHand
from dex_hand.skills.make_contact import MakeContact
from dex_hand.skills.establish_grasp import EstablishGrasp
from dex_hand.skills.apply_wrench import ApplyWrench
from dex_hand.skills.break_contact import BreakContact

def direct_action(self,name,args):
    if name=='stop':self.a.safe_hold();result={'stopped':True,'state':self.compact()}
    elif name=='set_joint_targets':
        duration=float(args['duration'])
        if not .02<=duration<=2:raise ValueError('duration must be .02..2 seconds')
        targets=self.a.target.copy()
        for k,v in args['targets'].items():
            i=int(k)
            if i<0 or i>=len(targets):raise ValueError('invalid joint index')
            targets[i]=float(v)
        self.a.command_joint_targets(targets)
        self.a.step(round(duration/self.a.dt));result={'state':self.compact()}
    else:raise ValueError('tool unavailable for Direct Agent')
    return result

def skill_action(self,name,args):
    registry={'SHAPE_HAND':lambda:ShapeHand(self.a).run('target',self.groups,profile=args.get('profile','PRESHAPE'),aperture=.04),
        'MAKE_CONTACT':lambda:MakeContact(self.a).run('target',self.groups),
        'ESTABLISH_GRASP':lambda:EstablishGrasp(self.a,self.probe).run('target',self.groups),
        'MAINTAIN_GRASP_enter':lambda:self.mode.enter('target',self.groups),
        'MAINTAIN_GRASP_query':lambda:self.mode.query(),'MAINTAIN_GRASP_exit':lambda:self.mode.exit(),
        'APPLY_WRENCH':lambda:ApplyWrench(self.a).run('target',self.groups),
        'BREAK_CONTACT':lambda:BreakContact(self.a).run('target',self.groups,support_state='FIXTURE' if self.task=='C' else 'SURFACE',retreat=.02 if self.task=='C' else .012)}
    if name not in registry:raise ValueError('tool unavailable for Skill Agent')
    out=registry[name]();result=out.to_dict() if hasattr(out,'to_dict') else out
    result['state']=self.compact()
    if result.get('status')=='FAILED':self.action_failures+=1;self.last_failed=True
    return result
